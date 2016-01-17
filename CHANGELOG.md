# Changelog

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

* Verwerken berichten gebeurt op aparte worker thread (voorkomt verloren berichten bij DVS bursts)
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

* Aantal extra vertalingen naar Engels voor oorzakentabel (opgeheven/vertraagde treinen)
* Treinnaam verhuisd naar treintips (HTTP interface)
* Vertaalde treinnaam bij IC Direct (waar treinnaamveld wordt misbruikt voor toeslaginfo)

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
* Grootte van trein- en stationstores en berichtenteller toegevoegd als ZMQ commando
* Diverse wijzigingsoorzaken vertaald naar Engels

## 1.0.0

* Eerste release
