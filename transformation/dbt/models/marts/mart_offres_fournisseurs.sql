{{ config(materialized='table') }}

-- Mart : Analyse consolidée par fournisseur
-- Grain : 1 ligne = 1 fournisseur x 1 date d'observation
with offres_enrichies as (
    select * from {{ ref('int_offres_produits') }}
),

kpis as (
    select
        supplier_id,
        observed_on,
        count(distinct offer_id) as total_offres,
        count(distinct product_id) as nb_produits_distincts,
        sum(available_units) as total_unites_disponibles,
        round(avg(price_eur), 2) as prix_moyen_eur,
        min(price_eur) as prix_min_eur,
        max(price_eur) as prix_max_eur,
        round(sum(valeur_stock_estimee_eur), 2) as valeur_totale_stock_eur
    from offres_enrichies
    group by supplier_id, observed_on
)

select * from kpis
order by supplier_id, observed_on
