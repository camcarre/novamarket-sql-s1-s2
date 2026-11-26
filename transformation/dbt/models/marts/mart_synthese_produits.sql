{{ config(materialized='table') }}

-- Mart : Analyse concurrentielle par produit
-- Grain : 1 ligne = 1 produit
with offres_enrichies as (
    select * from {{ ref('int_offres_produits') }}
),

synthese_marche as (
    select
        product_id,
        product_name,
        count(distinct supplier_id) as nb_fournisseurs,
        min(price_eur) as meilleur_prix_eur,
        max(price_eur) as pire_prix_eur,
        round(avg(price_eur), 2) as prix_moyen_eur,
        sum(available_units) as total_unites_marche
    from offres_enrichies
    group by product_id, product_name
)

select * from synthese_marche
order by product_id
