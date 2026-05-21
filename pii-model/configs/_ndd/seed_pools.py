# SPDX-FileCopyrightText: Copyright (c) 2026 Ranymizer
# SPDX-License-Identifier: Apache-2.0
"""Static seed pools used by the Swedish PII recipe.

100 % fabricated. No real Swedish citizens, no real medical records,
no real congregational data. The sensitive pools (`_HEALTH`,
`_RELIGION_ETHNICITY`) are short clinical / membership phrases drawn from
public-domain Swedish vocabulary.
"""

from __future__ import annotations

_SWEDISH_FIRST_NAMES = [
    "Anna",
    "Erik",
    "Maria",
    "Lars",
    "Karin",
    "Anders",
    "Eva",
    "Johan",
    "Sara",
    "Mikael",
    "Linda",
    "Per",
    "Helena",
    "Magnus",
    "Emma",
    "Daniel",
    "Sofia",
    "Andreas",
    "Lena",
    "Mattias",
    "Ingrid",
    "Stefan",
    "Margareta",
    "Niklas",
    "Astrid",
    "Oskar",
    "Greta",
    "Henrik",
]

_SWEDISH_SURNAMES = [
    "Andersson",
    "Johansson",
    "Karlsson",
    "Nilsson",
    "Eriksson",
    "Larsson",
    "Olsson",
    "Persson",
    "Svensson",
    "Gustafsson",
    "Pettersson",
    "Jonsson",
    "Jansson",
    "Lindberg",
    "Lindgren",
    "Lindström",
    "Lindqvist",
    "Bergström",
    "Berglund",
    "Sandberg",
    "Forsberg",
    "Sjöberg",
    "Wallin",
    "Ek",
    "Ekborg",
]

_SWEDISH_STREETS = [
    "Storgatan",
    "Kungsgatan",
    "Drottninggatan",
    "Sveavägen",
    "Vasagatan",
    "Östermalmstorg",
    "Götgatan",
    "Hornsgatan",
    "Birger Jarlsgatan",
    "Strandvägen",
    "Folkungagatan",
    "Tegnérgatan",
    "Karlavägen",
    "Valhallavägen",
]

_SWEDISH_CITIES = [
    ("Stockholm", "111 22"),
    ("Göteborg", "411 03"),
    ("Malmö", "211 18"),
    ("Uppsala", "753 21"),
    ("Linköping", "582 19"),
    ("Västerås", "722 12"),
    ("Örebro", "702 11"),
    ("Norrköping", "602 21"),
    ("Helsingborg", "252 25"),
    ("Lund", "222 22"),
    ("Umeå", "903 26"),
    ("Gävle", "802 67"),
]

_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "telia.com", "icloud.com"]

_COMPANY_PREFIXES = ["Nordic", "Svensk", "Stockholm", "Göteborgs", "Skånes"]
_COMPANY_TRADES = ["Konsult", "Bygg", "Handel", "Service", "Teknik"]

# Diversifier pools sampled directly by NDD `CategorySamplerParams`.

_DATE_POOL = [
    "2024-05-20",
    "2025-01-15",
    "20 maj 2024",
    "15 januari 2025",
    "2024-12-03",
    "3 december 2024",
]

_URL_POOL = [
    "https://www.skatteverket.se",
    "https://swish.nu",
    "https://www.bolagsverket.se",
    "https://min.handelsbanken.se",
    "https://www.fk.se",
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
]
