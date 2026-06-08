# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Curated seed pools sampled directly by NDD `CategorySamplerParams`.

Person names, addresses, companies, phone numbers and the Swedish identifiers
(`personnummer`, `organisationsnummer`) are NOT here — they come from Faker's
`sv_SE` locale via `seeds.py`, which gives an effectively unbounded,
format-valid Swedish vocabulary (a detector must generalise beyond any fixed
list). What remains here are the small, deliberately hand-curated sets:

  - `_DOMAINS`               email domains for name-derived addresses.
  - `_DATE_POOL`, `_URL_POOL`  short fixed pools for those low-cardinality labels.
  - `_HEALTH_POOL`,
    `_RELIGION_ETHNICITY_POOL` GDPR Art. 9 sensitive phrases — kept curated and
                              auditable on purpose (so a kommun DPIA can cite the
                              exact, fabricated vocabulary), never machine-sampled.

100 % fabricated. No real Swedish citizens, no real medical records, no real
congregational data.
"""

from __future__ import annotations

_DOMAINS = [
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "telia.com",
    "icloud.com",
    "live.se",
    "spray.se",
    "bredband.net",
    "comhem.se",
    "yahoo.se",
]

_DATE_POOL = [
    "2024-05-20",
    "2025-01-15",
    "20 maj 2024",
    "15 januari 2025",
    "2024-12-03",
    "3 december 2024",
    "2023-08-11",
    "11 augusti 2023",
    "2024-02-29",
    "29 februari 2024",
    "2025-06-30",
    "30 juni 2025",
    "1 april 2024",
    "2024-04-01",
    "den 17 oktober 2023",
    "2023-10-17",
    "7 mars 2025",
    "2025-03-07",
    "2024-09-14",
    "14 september 2024",
    "23/11 2024",
    "2024-07-04",
    "4 juli 2024",
    "fredagen den 12 januari 2024",
]

_URL_POOL = [
    "https://www.skatteverket.se",
    "https://swish.nu",
    "https://www.bolagsverket.se",
    "https://min.handelsbanken.se",
    "https://www.fk.se",
    "https://www.1177.se",
    "https://www.kronofogden.se",
    "https://www.csn.se",
    "https://www.pensionsmyndigheten.se",
    "https://www.arbetsformedlingen.se",
    "https://app.swedbank.se/login",
    "https://internetbanken.seb.se",
    "https://www.nordea.se",
    "https://www.kivra.com",
    "https://mitt.bankid.com",
    "https://www.transportstyrelsen.se",
    "https://www.migrationsverket.se",
    "https://etjanst.stockholm.se",
    "https://www.minpension.se",
    "https://www.verksamt.se",
    "https://www.hallakonsument.se",
    "https://www.polisen.se/tjanster",
]

_HEALTH_POOL = [
    "diabetes typ 2",
    "ADHD",
    "depression",
    "astma",
    "Crohns sjukdom",
    "sjukskriven på heltid",
    "rullstolsburen",
    "Metformin 500 mg",
    "Sertralin 50 mg",
    "fysioterapi 1 gång/vecka",
    "högt blodtryck",
    "epilepsi",
    "reumatoid artrit",
    "bipolär sjukdom typ 1",
    "ulcerös kolit",
    "celiaki (glutenintolerans)",
    "KOL, stadium 2",
    "diabetes typ 1, insulinpump",
    "utmattningssyndrom",
    "generaliserat ångestsyndrom",
    "Levaxin 75 mikrogram",
    "Citalopram 20 mg dagligen",
    "Concerta 36 mg",
    "väntar på höftledsoperation",
    "remiss till psykiatrisk öppenvård",
    "dialysbehandling tre gånger i veckan",
    "pågående cellgiftsbehandling",
    "hörselnedsättning, använder hörapparat",
    "synskadad, ledarhund",
    "allergisk mot penicillin",
]

_RELIGION_ETHNICITY_POOL = [
    "medlem i Svenska kyrkan",
    "katolik",
    "muslim",
    "judisk församling",
    "ateist",
    "samiskt ursprung",
    "född i Syrien",
    "talar arabiska som modersmål",
    "medlem i IF Metall",
    "medlem i Kommunal",
    "tillhör pingströrelsen",
    "ortodox kristen",
    "buddhist",
    "hindu",
    "medlem i frikyrkan EFS",
    "bär hijab av religiösa skäl",
    "firar ramadan",
    "konverterade till kristendomen",
    "talar finska som modersmål",
    "tornedalsk bakgrund",
    "kurdiskt ursprung",
    "född i Somalia",
    "uppvuxen i Chile",
    "talar sydsamiska",
    "medlem i Jehovas vittnen",
    "går regelbundet till moskén",
    "medlem i Hyresgästföreningen",
    "fackligt aktiv i Vision",
    "vegan av etiska skäl",
    "romsk bakgrund",
]

# GDPR Art. 10 — criminal offences / convictions. Generic, fabricated offence
# phrases (no real cases, no real defendants). Kept curated + hashed for the
# same DPIA-citation reason as the Art. 9 pools.
_CRIMINAL_POOL = [
    "misstänkt för stöld",
    "dömd för misshandel",
    "villkorlig dom",
    "dagsböter 50 om 200 kr",
    "skyddstillsyn",
    "åtalad för rattfylleri",
    "narkotikabrott, ringa",
    "tidigare straffad",
    "pågående förundersökning",
    "frikänd i tingsrätten",
    "dömd till fängelse i 6 månader",
    "anhållen i sin frånvaro",
    "häktad på sannolika skäl",
    "misstänkt för grov stöld",
    "åtalad för bedrägeri",
    "dömd för olovlig körning",
    "samhällstjänst 80 timmar",
    "kontaktförbud utfärdat",
    "villkorligt frigiven",
    "indraget körkort efter fortkörning",
    "misstänkt för skadegörelse",
    "dömd för olaga hot",
    "förundersökning nedlagd",
    "ströks ur belastningsregistret",
    "ungdomsvård enligt LVU",
    "dömd för snatteri",
    "böter för förargelseväckande beteende",
    "misstänkt för rattonykterhet",
    "överklagat domen till hovrätten",
    "noteringar i belastningsregistret",
]
