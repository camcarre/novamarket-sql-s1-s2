{{ config(materialized='view') }}

-- Staging des offres fournisseurs
-- Grain : 1 ligne = 1 observation d'offre à une date donnée (offer_id, observed_on)
with source as (
    select * from {{ source('fournisseur', 'offres') }}
),

renamed as (
    select
        trim(offer_id) as offer_id,
        trim(supplier_id) as supplier_id,
        product_id,
        price_cents,
        round(price_cents / 100.0, 2) as price_eur,
        trim(currency) as currency,
        available_units,
        observed_on,
        loaded_at
    from source
)

select * from renamed
