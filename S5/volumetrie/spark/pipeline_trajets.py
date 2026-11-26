"""M4 - Pipeline PySpark complet sur l'extraction streaming NYC Taxi (janvier 2024).

Étapes :
1. Démarrage d'une SparkSession locale.
2. Lecture du JSONL (M2/M3) et du référentiel zones.csv + inspection des schémas.
3. Typage strict, filtrage qualité et calcul de variables métier (distance_km, vitesse_kmh).
4. Contrôle d'unicité de la clé LocationID et détection des non-appariements (left_anti).
5. Jointure inner, vérification des effectifs avant/après (aucune multiplication de lignes).
6. Agrégation par Borough, inspection du partitionnement et du plan explain().
7. Écriture Parquet en mode errorifexists puis relecture de contrôle.
"""
import argparse
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sortie",
        type=Path,
        help="Dossier de sortie Parquet inédit (ex: /tmp/s5_novamarket_v1)",
    )
    parser.add_argument(
        "--entree",
        default="S5/volumetrie/streaming/extraction_yellow_2024_01.jsonl",
        help="Fichier JSONL produit en M2/M3",
    )
    parser.add_argument(
        "--zones",
        default="S5/volumetrie/secours/zones.csv",
        help="Table de référence des zones NYC",
    )
    args = parser.parse_args()

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("novamarket-s5-trajets")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

    try:
        # 1. Lecture brute et inspection des schémas
        trajets_bruts = spark.read.json(args.entree)
        zones_brutes = spark.read.option("header", True).csv(args.zones)

        print("\n=== 1. Schémas lus ===")
        trajets_bruts.printSchema()
        zones_brutes.printSchema()
        print("Partitions trajets avant traitement :", trajets_bruts.rdd.getNumPartitions())

        # 2. Typage strict, filtrage et calcul de variables métier
        trajets = (
            trajets_bruts.select(
                F.col("Start_Zone").cast("int").alias("start_zone"),
                F.col("Trip_Distance").cast("double").alias("trip_distance_miles"),
                F.col("Trip_Duration").cast("double").alias("trip_duration_sec"),
            )
            .where(
                F.col("start_zone").isNotNull()
                & (F.col("trip_distance_miles") > 0)
                & (F.col("trip_duration_sec") > 0)
            )
            .withColumn("distance_km", F.round(F.col("trip_distance_miles") * 1.60934, 3))
            .withColumn(
                "vitesse_kmh",
                F.round(
                    (F.col("trip_distance_miles") * 1.60934)
                    / (F.col("trip_duration_sec") / 3600.0),
                    2,
                ),
            )
        )

        zones = zones_brutes.select(
            F.col("LocationID").cast("int").alias("location_id"),
            F.trim(F.col("Borough")).alias("borough"),
            F.trim(F.col("Zone")).alias("zone_name"),
            F.trim(F.col("service_zone")).alias("service_zone"),
        )

        # 3. Contrôle de la clé de jointure dans zones.csv
        nb_zones = zones.count()
        nb_zones_uniques = zones.select("location_id").distinct().count()
        print(f"\n=== 2. Contrôle clé zones.csv ===")
        print(f"Lignes zones : {nb_zones} | LocationID distincts : {nb_zones_uniques}")
        assert nb_zones == nb_zones_uniques, "Doublon détecté sur LocationID dans zones.csv !"

        # 4. Détection des non-appariements (left_anti)
        nb_avant = trajets.count()
        non_apparies = trajets.join(
            zones, trajets.start_zone == zones.location_id, how="left_anti"
        )
        nb_non_apparies = non_apparies.count()
        print(f"\n=== 3. Contrôle avant/après jointure ===")
        print(f"Trajets avant jointure    : {nb_avant}")
        print(f"Non-appariements (anti)   : {nb_non_apparies}")
        if nb_non_apparies > 0:
            print("Exemples de Start_Zone non appariées :")
            non_apparies.groupBy("start_zone").count().show(10)

        # 5. Jointure inner et vérification anti-multiplication
        trajets_enrichis = trajets.join(
            zones, trajets.start_zone == zones.location_id, how="inner"
        ).drop("location_id")

        nb_apres = trajets_enrichis.count()
        print(f"Trajets après jointure    : {nb_apres}")
        assert nb_apres == nb_avant - nb_non_apparies, (
            "Incohérence de volume après jointure (multiplication ou perte inattendue) !"
        )

        # 6. Agrégation par Borough
        synthese_borough = (
            trajets_enrichis.groupBy("borough")
            .agg(
                F.count("*").alias("nb_trajets"),
                F.round(F.avg("distance_km"), 2).alias("distance_moy_km"),
                F.round(F.avg("trip_duration_sec") / 60.0, 2).alias("duree_moy_min"),
                F.round(F.avg("vitesse_kmh"), 2).alias("vitesse_moy_kmh"),
            )
            .orderBy(F.desc("nb_trajets"))
        )

        print("\n=== 4. Partitionnement & Plan d'exécution (explain) ===")
        print("Partitions après agrégation :", synthese_borough.rdd.getNumPartitions())
        synthese_borough.explain()

        # 7. Écriture Parquet (sans écrasement silencieux) puis relecture
        print(f"\n=== 5. Export Parquet vers {args.sortie} ===")
        synthese_borough.write.mode("errorifexists").parquet(str(args.sortie))

        print("\n=== 6. Relecture du Parquet écrit ===")
        relu = spark.read.parquet(str(args.sortie)).orderBy(F.desc("nb_trajets"))
        relu.show(truncate=False)
        print("Total lignes relues dans le Parquet :", relu.count())

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
