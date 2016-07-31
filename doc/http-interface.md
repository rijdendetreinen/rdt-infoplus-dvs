HTTP interface
==============

RDT infoplus-dvs biedt een REST API met de volgende mogelijkheden:

 - Opvragen actuele vertrektijden per station
 - Opvragen van ritdetails
 - Opvragen van de detail van één vertrek (rit vanaf vertrekstation)
 - Opvragen systeemstatus

De uitvoer van reisinformatie is beschikbaar in Nederlands en Engels.

Opvragen vertrektijden per station
----------------------------------

`/v2/station/<station>`

Geeft een array met alle vertrektijden voor het opgegeven station,
gesorteerd op vertrektijd. `<station>` is de stationscode (niet
hoofdlettergevoelig), zoals `O` (Oss) of `UT` (Utrecht Centraal).

Optionele parameters:

 - `taal=<taal>`, waarbij `<taal>` `nl` of `en` is. Hiermee worden
   opmerkingen en reistips vertaald naar de juiste taal.
 - `verbose=true`. Wanneer de verbose vertrektijden worden opgevraagd
   worden de treinvleugels en bijbehorend materieel meegestuurd in de
   response. Deze worden weggelaten bij een niet-verbose request.

### Voorbeelden

 - `/v2/station/zvt`
 - `/v2/station/zvt?verbose=true`
 - `/v2/station/zvt?taal=en&verbose=true`

```json
{
  "system_status": "RECOVERING",
  "result": "OK",
  "vertrektijden": [
    {
      "status": "0",
      "via": "Haarlem, Sloterdijk",
      "bestemming": "Amsterdam Centraal",
      "vleugels": [
        {
          "bestemming": "Amsterdam Centraal",
          "mat": [
            [
              "DDZ-4",
              "Amsterdam CS",
              null
            ]
          ]
        }
      ],
      "vervoerder": "NS",
      "spoor": "2",
      "treinNr": "5450",
      "soort": "Sprinter",
      "vertraging": 0,
      "soortAfk": "SPR",
      "opgeheven": false,
      "vertrek": "2016-07-31T16:39:00+02:00",
      "sprWijziging": false,
      "opmerkingen": [],
      "tips": [],
      "id": "5450"
    },
    {
      "status": "0",
      "via": null,
      "bestemming": "Haarlem",
      "vleugels": [
        {
          "bestemming": "Haarlem",
          "mat": [
            [
              "DDZ-4",
              "Haarlem",
              null
            ]
          ]
        }
      ],
      "vervoerder": "NS",
      "spoor": "1",
      "treinNr": "15450",
      "soort": "Sprinter",
      "vertraging": 0,
      "soortAfk": "SPR",
      "opgeheven": false,
      "vertrek": "2016-07-31T16:56:00+02:00",
      "sprWijziging": false,
      "opmerkingen": [],
      "tips": [],
      "id": "15450"
    }
  ]
}
```

Opvragen ritdetails
-------------------

 - `/v2/trein/<trein>`
 - `/v2/trein/<trein>/<datum>`

Geeft een dict terug met de ritdetails van de opgevraagde trein.
`<trein>` is het ID van een trein (meestal ritnummer, matcht met veld
`id` uit het overzicht met vertrektijden), `<datum>` is de gewenste
dienstregelingsdatum in YYYY-MM-DD formaat of de string `vandaag` voor
de huidige dienstregelingsdatum.

Wanneer beschikbaar wordt alle informatie teruggegeven die via DVS
beschikbaar is. Indien deze gegevens niet (meer) beschikbaar zijn wordt
teruggevallen op de koppeling met RDT serviceinfo (met ARNU of IFF als
bron).

Bij de ritdetails is geen materieelinformatie beschikbaar.

Optionele parameters:

 - `taal=<taal>`, waarbij `<taal>` `nl` of `en` is. Hiermee worden
   opmerkingen en reistips vertaald naar de juiste taal.

### Voorbeelden

 - `/v2/trein/5422`
 - `/v2/trein/5422/vandaag`
 - `/v2/trein/5422/2016-08-01?taal=en`
 
```json
{
  "source": "serviceinfo",
  "system_status": null,
  "result": "OK",
  "trein": {
    "status": 0,
    "via": null,
    "bestemming": "Amsterdam Centraal",
    "vleugels": [
      {
        "stopstations": [
          {
            "aankomstspoor": "2",
            "vertrekspoor": "2",
            "code": "zvt",
            "vertragingVertrek": 0,
            "aankomst": null,
            "naam": "Zandvoort aan Zee",
            "vertrek": "2016-08-01T09:39:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "2",
            "vertrekspoor": "2",
            "code": "ovn",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T09:46:00+02:00",
            "naam": "Overveen",
            "vertrek": "2016-08-01T09:46:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "1",
            "vertrekspoor": "1",
            "code": "hlm",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T09:50:00+02:00",
            "naam": "Haarlem",
            "vertrek": "2016-08-01T09:51:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "1",
            "vertrekspoor": "1",
            "code": "hlms",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T09:54:00+02:00",
            "naam": "Haarlem Spaarnwoude",
            "vertrek": "2016-08-01T09:54:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "1",
            "vertrekspoor": "1",
            "code": "hwzb",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T09:59:00+02:00",
            "naam": "Halfweg-Zwanenburg",
            "vertrek": "2016-08-01T09:59:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "8",
            "vertrekspoor": "8",
            "code": "ass",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T10:04:00+02:00",
            "naam": "Amsterdam Sloterdijk",
            "vertrek": "2016-08-01T10:04:00+02:00",
            "sprWijziging": false,
            "vertragingAankomst": 0
          },
          {
            "aankomstspoor": "1",
            "vertrekspoor": "1",
            "code": "asd",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T10:10:00+02:00",
            "naam": "Amsterdam Centraal",
            "vertrek": null,
            "sprWijziging": false,
            "vertragingAankomst": 0
          }
        ],
        "bestemming": "Amsterdam Centraal",
        "mat": []
      }
    ],
    "vervoerder": "NS",
    "spoor": "2",
    "treinNr": 5422,
    "soort": "Sprinter",
    "vertraging": 0,
    "soortAfk": "SPR",
    "opgeheven": false,
    "vertrek": "2016-08-01T09:39:00+02:00",
    "sprWijziging": false,
    "opmerkingen": [],
    "tips": [],
    "id": 5422
  }
}
```

Opvragen vertrekdetails
-----------------------

`/v2/trein/<trein>/<datum>/<station>`

Geeft een dict terug met de ritdetails van de opgevraagde trein, zoals
deze vertrekt vanaf het opgegeven station. Materieelinformatie (indien
beschikbaar voor de rit) wordt teruggegeven zoals deze op het
vertrekstation verwacht wordt. De stopstations beginnen vanaf het
station na het opgegeven vertrekstation.

De parameters en het fallbackmechanisme zijn gelijk als bij het opvragen
van ritdetails.

Optionele parameters:

 - `taal=<taal>`, waarbij `<taal>` `nl` of `en` is. Hiermee worden
   opmerkingen en reistips vertaald naar de juiste taal.

### Voorbeelden

 - `/v2/trein/5422/vandaag/ass`
 - `/v2/trein/5422/vandaag/ass?taal=en`
 - `/v2/trein/5422/2016-08-01/ass?taal=en`

```json
{
  "source": "serviceinfo",
  "system_status": null,
  "result": "OK",
  "trein": {
    "status": 0,
    "via": null,
    "bestemming": "Amsterdam Centraal",
    "vleugels": [
      {
        "stopstations": [
          {
            "aankomstspoor": "1",
            "vertrekspoor": "1",
            "code": "asd",
            "vertragingVertrek": 0,
            "aankomst": "2016-08-01T10:10:00+02:00",
            "naam": "Amsterdam Centraal",
            "vertrek": null,
            "sprWijziging": false,
            "vertragingAankomst": 0
          }
        ],
        "bestemming": "Amsterdam Centraal",
        "mat": []
      }
    ],
    "vervoerder": "NS",
    "spoor": "8",
    "treinNr": 5422,
    "soort": "Sprinter",
    "vertraging": 0,
    "soortAfk": "SPR",
    "opgeheven": false,
    "vertrek": "2016-08-01T10:04:00+02:00",
    "sprWijziging": false,
    "opmerkingen": [],
    "tips": [],
    "id": 5422
  }
}
```

Statusinformatie
----------------

`/v2/status`

Geeft de systeemstatus terug: de systeemmodus (`UNKNOWN`, `RECOVERING`
of `UP`), eventuele starttijdstip van downtime, en eventuele tijdstip
van het starten van recovery.

### Voorbeeld

 - `/v2/status`

```json
{
  "data": {
    "status": "DOWN",
    "down_since": "2016-07-31 09:59:18.937570",
    "recovering_since": "2016-07-31 13:41:54.203320"
  },
  "result": "OK"
}
```

Legacy URLs
-----------

 - `/v1/station/<station>`
 - `/v1/station/<station>/<taal>`
 - `/v1/trein/<trein>/<station>`
 - `/v1/trein/<trein>/<station>/<taal>`
 - `/v1/status`
