{{ config(
    engine='MergeTree()',
    order_by='(code_departement, horodatage)',
    partition_by='toYYYYMM(horodatage)'
) }}

select
    assumeNotNull(code_departement) as code_departement,
    assumeNotNull(horodatage) as horodatage,
    temperature_2m,
    wind_speed_100m,
    shortwave_radiation,
    precipitation,
    snowfall,
    snow_depth,
    longitude_grille,
    latitude_grille,
    altitude,
    date_extraction
from {{ source('bronze', 'meteo_horaire') }}
