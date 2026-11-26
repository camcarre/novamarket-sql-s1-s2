{{ config(materialized='ephemeral') }}

-- Intermediate : enrichissement des offres avec les informations produits
-- Matérialisé en CTE éphémère pour réutilisation propre sans table physique intermédiaire
with offres as (
    select * from {{ ref('stg_offres') }}
),

produits as (
    select * from {{ ref('stg_products') }}
),

jointure as (
    select
        o.offer_id,
        o.supplier_id,
        o.product_id,
        p.product_name,
        p.category_id,
        o.price_cents,
        o.price_eur,
        o.currency,
        o.available_units,
        round(o.price_eur * o.available_units, 2) as valeur_stock_estimee_eur,
        o.observed_on
    from offres o
    inner join produits p on o.product_id = p.product_id
)

select * from jointure
