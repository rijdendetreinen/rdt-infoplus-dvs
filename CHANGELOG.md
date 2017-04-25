# Changelog

## 1.5.7

* Tel ongeldige berichten niet mee voor aantal berichten
  (in verband met downtime-detectie)

## 1.5.6

* Docker containers toegevoegd

## 1.5.5

* Vertalingen bijgewerkt

## 1.5.4

* Vertalingen bijgewerkt
* Voorbeeldconfiguratie aangepast (envelope standaard ingesteld)

## 1.5.3

* Vertalingen bijgewerkt

## 1.5.2

* Verwerk attribuut voor opgeheven vertrek uit DVS injecties
* Geef bij ritinfo geen stationsopmerkingen terug

## 1.5.1

* Geef status door van opgeheven stops (uit serviceinfo)

## 1.5.0

* Let op: HTTP interface is gewijzigd. Bestaande URL's hebben nu /v1 als
  prefix, gebruik /v2 voor nieuwe toepassingen
* Opvragen ritinformatie toegevoegd
* Voor ritinfo en vertrekdetails is nu een fallback op rdt-serviceinfo
* Ritten worden tot 120 minuten na vertrek in geheugen bewaard
* Ondersteuning voor DVS injecties met vertraging
* Documentatie HTTP interface verbeterd (zie /doc)
* Vertalingen bijgewerkt

## 1.4.3

* Detectie op DVS-berichten die minder dan 70 minuten voor vertrek
  worden ontvangen
* Vertalingen bijgewerkt

## 1.4.2

* Vertalingen bijgewerkt

## 1.4.1

* Geen melding 'voorste treindeel tot' voor locomotieven
* Notatie 186-locs
* Vertalingen bijgewerkt

## 1.4.0

* Ondersteuning voor InfoPlus DVS-PPV
* Materieelnummers (uit DVS-PPV)
* Attendering op afwijkende eindbestemming treinstellen
* Ondersteuning voor nieuwe oorzaakteksten
* Meer debugopties mogelijk

## 1.3.1

* Optie voor ZMQ envelope toegevoegd

## 1.3.0

* Koppeling met rdt-serviceinfo in HTTP-interface
* Nieuw formaat injecties
* Configuratie voor HTTP-interface naar eigen http.yaml config

## 1.2.7

* Bugfix voor HTTP interface in combinatie met geinjecteerde ritten

## 1.2.6

* Gaat nu beter om met negatieve vertraging

## 1.2.5

* Verwerken berichten gebeurt op aparte worker thread (voorkomt verloren
  berichten bij DVS bursts)
* ZeroMQ HWM (high water mark) op onbeperkt gezet
* Vertalingen bijgewerkt
* Kleine bugfixes, code opgeschoond

## 1.2.4

* Voorbereid op hernoeming vervoerder 'NS Interna' naar 'NS Int'

## 1.2.3

* Dubbele actuele eindbestemming wordt samengevoegd (#3)
* Vervoerder 'Locon Bene' vervangen door 'Locon Benelux' (#4)
* Changelog toegevoegd

## 1.2.2

* Vervoerder 'NS Interna' vervangen door 'NS International' (#2)
* Documentatie verbeterd

## 1.2.1

* Aantal extra vertalingen naar Engels voor oorzakentabel
  (opgeheven/vertraagde treinen)
* Treinnaam verhuisd naar treintips (HTTP interface)
* Vertaalde treinnaam bij IC Direct (waar treinnaamveld wordt misbruikt
  voor toeslaginfo)

## 1.2.0a

* README en licentie toegevoegd
* Aantal testtools verplaatst
* rdt-infoplus-dvs is vanaf nu open source beschikbaar via GitHub

## 1.2.0

* Downtimedetectie toegevoegd
* Monitoringscripts voor Nagios en Munin toegevoegd
* Verbeterde logging

## 1.1.2

* Verbose-mode toegevoegd voor vertrektijden /station (JSON-interface)
* Engelse vertalingen uitgebreid
* HTTP 500 error bij exceptions in JSON-interface
* Ontbrekende vertalingen worden nu gelogd

## 1.1.1

* Betere omgang met ZeroMQ timeouts

## 1.1.0

* Interface voor injecties (vanuit IFF) toegevoegd

## 1.0.4

* Treinnaam toegevoegd aan JSON interface
* Vertaalde oorzaken uitgebreid

## 1.0.3

* Diverse reistips worden niet meer meegegeven aan opgeheven treinen
* Lijst met vertaalde oorzaken uitgebreid

## 1.0.2

* Melding met vertragingsoorzaak toegevoegd (indien aanwezig)
* Logging voor verouderde of dubbele DVS-berichten
* Munin plugin voor verouderde of dubbele DVS-berichten
* Lijst met vertaalde oorzaken uitgebreid

## 1.0.1

* Munin plugins toegevoegd
* Grootte van trein- en stationstores en berichtenteller toegevoegd als
  ZMQ commando
* Diverse wijzigingsoorzaken vertaald naar Engels

## 1.0.0

* Eerste release
