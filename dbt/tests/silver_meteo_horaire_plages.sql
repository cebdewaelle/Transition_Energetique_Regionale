-- Valeurs physiquement plausibles en France métropolitaine. Renvoie les lignes hors plage.
select
    code_departement,
    horodatage,
    temperature_2m,
    wind_speed_100m,
    shortwave_radiation,
    precipitation,
    snowfall,
    snow_depth,
    longitude_grille,
    latitude_grille,
    altitude
from {{ ref('silver_meteo_horaire') }}
where temperature_2m not between -40 and 55
    or wind_speed_100m not between 0 and 70
    or shortwave_radiation not between 0 and 1400
    or precipitation not between 0 and 200
    or snowfall not between 0 and 100
    or snow_depth not between 0 and 20
    or longitude_grille not between -6 and 10
    or latitude_grille not between 41 and 52
    or altitude not between -10 and 4810
