-- Aucun mois manquant entre le premier et le dernier mois chargés. Renvoie les trous.
with mois as (
    select distinct toStartOfMonth(horodatage) as mois
    from {{ ref('silver_meteo_horaire') }}
),

ecarts as (
    select
        mois,
        lagInFrame(mois) over (
            order by mois
            rows between unbounded preceding and unbounded following
        ) as mois_precedent
    from mois
)

select mois_precedent, mois
from ecarts
where mois_precedent != toDate32('1970-01-01')
    and addMonths(mois_precedent, 1) != mois
