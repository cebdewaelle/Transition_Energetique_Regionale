-- Chaque mois présent doit contenir toutes les heures de tous les départements du référentiel.
with attendu as (
    select count() as nb_departements from {{ source('bronze', 'ref_departements') }}
),

par_mois as (
    select
        toStartOfMonth(horodatage) as mois,
        count() as nb_lignes,
        uniqExact(code_departement) as nb_departements,
        uniqExact(horodatage) as nb_heures
    from {{ ref('silver_meteo_horaire') }}
    group by mois
)

select par_mois.*
from par_mois
cross join attendu
where par_mois.nb_departements != attendu.nb_departements
    or par_mois.nb_heures != toDayOfMonth(toLastDayOfMonth(par_mois.mois)) * 24
    or par_mois.nb_lignes != par_mois.nb_heures * attendu.nb_departements
