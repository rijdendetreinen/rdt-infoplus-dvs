# HTTP interface

RDT infoplus-dvs biedt een REST API met de volgende mogelijkheden:

 - Opvragen actuele vertrektijden per station
 - Opvragen van ritdetails
 - Opvragen van de detail van één vertrek (rit vanaf vertrekstation)
 - Opvragen systeemstatus

De uitvoer van reisinformatie is beschikbaar in Nederlands en Engels.

## Opvragen vertrektijden per station

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

## Opvragen ritdetails

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

## Opvragen vertrekdetails

`/v2/trein/<trein>/<datum>/<station>`

Geeft een dict terug met de ritdetails van de opgevraagde trein, zoals
deze vertrekt vanaf het opgegeven station. Materieelinformatie (indien
beschikbaar voor de rit) wordt teruggegeven zoals deze op het
vertrekstation verwacht wordt. De stopstations beginnen vanaf het
opgegeven vertrekstation.

De parameters en het fallbackmechanisme zijn gelijk als bij het opvragen
van ritdetails.

Optionele parameters:

 - `taal=<taal>`, waarbij `<taal>` `nl` of `en` is. Hiermee worden
   opmerkingen en reistips vertaald naar de juiste taal.

## Statusinformatie

`/v2/status`

Geeft de systeemstatus terug: de systeemmodus (`UNKNOWN`, `RECOVERING`
of `UP`), eventuele starttijdstip van downtime, en eventuele tijdstip
van het starten van recovery.

## Legacy URLs

 - `/v1/station/<station>`
 - `/v1/station/<station>/<taal>`
 - `/v1/trein/<trein>/<station>`
 - `/v1/trein/<trein>/<station>/<taal>`
 - `/v1/status`
