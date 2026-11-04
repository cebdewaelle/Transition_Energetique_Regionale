-- Une seule ligne par département et par heure. Renvoie les doublons.
select code_departement, horodatage, count() as nb_lignes
from {{ ref('silver_meteo_horaire') }}
group by code_departement, horodatage
having nb_lignes > 1
