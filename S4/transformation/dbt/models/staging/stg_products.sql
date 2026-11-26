{{ config(materialized='view') }}

-- Staging du catalogue des produits
-- Grain : 1 ligne = 1 produit
with source as (
    select * from {{ source('core', 'products') }}
),

renamed as (
    select
        product_id,
        trim(sku) as sku,
        trim(product_name) as product_name,
        category_id,
        first_listed_on
    from source
)

select * from renamed
