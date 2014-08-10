InfoPlus DVS daemon
===================

This is a Python daemon for receiving and parsing InfoPlus DVS messages. InfoPlus DVS is a message service from the [Dutch Railways](http://www.ns.nl/) containing live departure times. This application is for now only available in Dutch, therefore the rest of this this document will also be in Dutch. Feel free to request more information if you are interested in this project.

----

Dit is een Python daemon voor het ontvangen en verwerken van InfoPlus DVS-berichten. InfoPlus DVS is een dienst van [NS](http://www.ns.nl/) met berichten voor actuele vertrektijden. De borden met actuele vertrektijden op de stations gebruiken dezelfde brongegevens die met deze applicatie verwerkt kunnen worden.

Deze applicatie wordt sinds december 2013 stabiel gebruikt door de app en website van [Rijden de Treinen](http://www.rijdendetreinen.nl/) (zie voor een implementatie op basis van deze daemon de [actuele vertrektijden](http://vertrektijden.rijdendetreinen.nl/)).

InfoPlus DVS
------------

**InfoPlus** is een project van NS voor het verbeteren van digitale reisinformatie. **DVS** staat voor Dynamische Vertrek Staten. DVS-berichten zijn uitgebreide XML-documenten met daarin per trein de vertrektijd, eindbestemming, tussenstations, eventuele vertraging, wijzigingen, en meer belangrijke informatie. De uitgebreide specificatie van deze berichten is te vinden op de website van het NDOV-loket: [InfoPlus DVS-standaard](https://ndovloket.nl/helpdesk/kb/31/).

Je kunt een aansluiting krijgen op InfoPlus DVS via het [NDOV-loket](https://www.ndovloket.nl/). Meer informatie hierover is te vinden op de website van het NDOV-loket, een aansluiting geeft meteen ook toegang tot veel meer actuele ov-informatie in Nederland.

Het NDOV-loket ontsluit de gegevens via [ZeroMQ](http://zeromq.org/). Je kunt de DVS daemon rechtstreeks aansluiten op de ZMQ-server van het NDOV-loket of via de [universal sub-pubsub proxy](https://github.com/StichtingOpenGeo/universal); het laatste wordt aanbevolen. Door DVS worden dagelijks ca. 170.000 berichten afgeleverd; een eigen sub-pubsub maakt het mogelijk om efficiënt en binnen je eigen netwerk deze data te distribueren.

Installatie en werking
======================

Deze daemon is getest op Debian en Ubuntu.  
Requirements:

* Python 2
* python-bottle (HTTP interface)
* python-isodate
* python-lxml
* python-tz
* python-yaml
* python-zmq

Installatie
-----------

1. Clone dit repository (directory naar keuze)
2. Kopieer in config/ het bestand `dvs-server.yaml.dist` naar `dvs-server.yaml`
3. Pas de instellingen in dit bestand aan
4. Start de DVS daemon met `./dvs-daemon.py`

Iedere minuut wordt de systeemstatus op de terminal gelogd. In deze logmelding wordt tevens het aantal treinen gelogd. Dit aantal zou na het opstarten steeds verder op moeten lopen.

### Configuratie

Standaard bevat dvs-server.yaml de volgende elementen:

```
---
bindings:
    dvs_server: tcp://12.34.56.78:8100
    client_server: tcp://0.0.0.0:8120
    injector_server: tcp://0.0.0.0:8140

logging:
    log_config: config/logging.yaml
...

```

Belangrijk is dat hier de juiste gegevens worden ingevuld:

* **dvs_server:** De ZeroMQ-bronserver (van NDOVloket of eigen pub-subpub server)
* **client_server:** lokale ip-adres en poortnummer voor de dvs-daemon.  
  Deze interface wordt aangesproken door dvs_http.py/wsgi en dvs_dump.py.  
  0.0.0.0 betekent alle interfaces op het systeem.
* **injector_server:** lokale ip-adres en poortnummer van de injector interface.
  De injectorinterface is voor het injecteren van extra trein/busritten (bijvoorbeeld van treinvervangend vervoer bij werkzaamheden). De module om deze informatie uit de statische NS-dienstregeling te lezen en te injecteren is nog niet open-source. 

De interface die je bij `client_server` instelt is ook de interface waar andere tools zoals dvs_dump.py verbinding mee maken.

Gebruik
-------

Wanneer de daemon actief is kan deze rechtstreeks via ZMQ bevraagd worden. Zowel een commandline tool (dvs-dump.py) als een HTTP interface zijn standaard beschikbaar in dit project.

Om vertrektijden uit te kunnen lezen moet je het volgende doen:

1. Start de dvs-daemon.py om vertrektijden te ontvangen en te verwerken.
2. Controleer via de console-output of de logfiles of dvs-daemon berichten ontvangt. Iedere minuut wordt de systeemstatus gelogd.
3. Met dvs-dump.py kun je via de CLI de dvs-daemon bevragen (zie hieronder). Met dvs-http.py start je een HTTP webserver die een REST interface aanbiedt en JSON teruggeeft (zie hieronder).

Houd er rekening mee dat de database met vertrektijden zich langzaam vult na het starten: pas na 70 minuten is de database volledig geladen voor alle stations.

### dvs-dump.py

Met de tool `dvs-dump.py` kan de systeemstatus bevraagd worden en kunnen opdrachten naar de DVS server verstuurd worden. Enkele voorbeelden:

**Status opvragen**

```
$ ./dvs-dump.py status
DVS server: tcp://127.0.0.1:8120
Opdracht:   status
------------------

{   'down_since': datetime.datetime(2014, 4, 21, 23, 28, 34, 956069),
    'recovering_since': None,
    'status': 'UNKNOWN'}
Opdracht uitgevoerd binnen 0.0s
```

**Aantal verwerkte berichten**

```
$ ./dvs-dump.py count/msg
DVS server: tcp://127.0.0.1:8120
Opdracht:   count/msg
---------------------

86
Opdracht uitgevoerd binnen 0.0s
```

**Vertrektijden voor een station**

```
$ ./dvs-dump.py station/ns
DVS server: tcp://127.0.0.1:8120
Opdracht:   station/ns
----------------------

{   'data': {   '5683': <Trein SPR   5683 v2014-04-21 23:47:00+02:00 +0:05:29 NS   [1] -- [<station ZL Zwolle>]>},
    'status': {   'down_since': datetime.datetime(2014, 4, 21, 23, 28, 34, 956069),
                  'recovering_since': None,
                  'status': 'UNKNOWN'}}
Opdracht uitgevoerd binnen 0.03s
```

**Alle vertrektijden opvragen**

```
$ ./dvs-dump.py store/station
DVS server: tcp://127.0.0.1:8120
Opdracht:   store/station
-------------------------

{   'AH': {   '3083': <Trein IC    3083 v2014-04-21 23:34:00+02:00 +0:00:00 AH   [8] -- [<station NM Nijmegen>]>},
    'EDC': {   '31372': <Trein ST   31372 v2014-04-21 23:29:00+02:00 +0:00:00 EDC  [1] -- [<station AMF Amersfoort>]>},
    'NS': {   '5683': <Trein SPR   5683 v2014-04-21 23:47:00+02:00 +0:05:29 NS   [1] -- [<station ZL Zwolle>]>},
    'PT': {   '5683': <Trein SPR   5683 v2014-04-21 23:30:00+02:00 +0:06:50 PT   [1] -- [<station ZL Zwolle>]>},
    'SOG': {   '32083': <Trein ST   32083 v2014-04-21 23:27:00+02:00 +0:00:00 SOG  [1] -- [<station KRD Kerkrade Centrum>]>},
    'SWD': {   '37677': <Trein ST   37677 v2014-04-21 23:33:00+02:00 +0:01:07 SWD  [2] -- [<station RD Roodeschool>]>,
               '37790': <Trein ST   37790 v2014-04-21 23:27:00+02:00 +0:00:00 SWD  [1] -- [<station GN Groningen>]>},
    'VST': {   '5789': <Trein SPR   5789 v2014-04-21 23:27:00+02:00 +0:00:00 VST  [4] -- [<station WP Weesp>]>},
    'WZ': {   '5683': <Trein SPR   5683 v2014-04-21 23:59:00+02:00 +0:04:33 WZ   [1] -- [<station ZL Zwolle>]>}}
Opdracht uitgevoerd binnen 0.02s
```

Het is mogelijk om de host en poort aan te passen met de parameters `--server` en `--port`.

### HTTP interface

De HTTP interface kan voor ontwikkeldoeleinden gestart worden met de tool `dvs-http.py`. Deze tool start een [Bottle](http://bottlepy.org/docs/dev/index.html) ontwikkelserver op http://localhost:8080/ (of optioneel op een andere host/poort-combinatie). Voor productiedoeleinden kun je de WSGI-koppeling in `dvs-http.wsgi` gebruiken.

De HTTP-interface ontsluit een JSON webservice die reageert op de volgende URL's:

* `/station/<stationcode>` en `/station/<stationcode>/<taal>` - Geeft de vertrektijden per station terug. Specificeer optioneel 'nl' of 'en' als taalcode om wijzigingen en dergelijke te vertalen (standaard is Nederlands). Optionele parameters: `sorteer` met mogelijke waarden 'gepland', 'actueel', 'vertrek', of 'vertraging', en `verbose` (indien de waarde 'true' is wordt meer informatie teruggegeven).
* `/trein/<treinnummer>/<stationcode>` en `/trein/<treinnummer>/<stationcode>` - Geeft uitgebreide verbose per trein op een bepaald station terug, zoals de route per treinvleugel.
* `/status` - Geeft de systeemstatus terug (UP, DOWN, UNKNOWN of RECOVERING) en eventuele starttijd van downtime en recovertijd.

De HTTP-interface kan op een andere server draaien dan de daemon zelf. In het WSGI-bestand wordt de host ingesteld waarmee verbinding gemaakt wordt.

Aandachtspunten
---------------

Na de eerste keer opstarten zal het systeem de eerste ~80 minuten rapporteren dat het systeem niet UP is. De eerste tien minuten wordt informatie verzameld voor downtime-detectie, na tien minuten zal het systeem vaststellen dat het aan het herstellen is van downtime (status RECOVERING). Aangezien binnen DVS een tijdvenster van 70 minuten wordt aangehouden duurt het op dat moment nog 70 minuten totdat het systeem zichzelf als ongestoord meldt (status UP).

Het is mogelijk om het systeem op te starten met de gegevens die in het geheugen geladen waren tijdens het afsluiten. Start dan met:  
`dvs-daemon.py --lt --ls`

Het geheugengebruik kan, afhankelijk van het aantal DVS-berichten en het aantal requests, oplopen tot ca. 500 MB.

In de directory /logs/ worden logfiles bijgehouden. De logfiles worden automatisch gerotate worden wanneer ze groter dan 10MB groeien.

Koppeling met Munin en/of Nagios als monitoringsysteem is mogelijk; zie de directory /contrib/ voor een aantal voorbeelchecks.

Ontwikkeling
============

Deze applicatie is ontwikkeld in Python. Verbeteringen of uitbreidingen zijn van harte welkom! Ook wanneer je niet mee wilt ontwikkelen, maar in het gebruik wel bugs of andere problemen ervaart, kun je meehelpen door een issue aan te maken. Zie het document [Contributing](CONTRIBUTING.md) voor meer informatie.

Licentie
========

Deze applicatie wordt vrij verspreid op basis van de GNU General Publice License (GPL) versie 3.

Een belangrijke voorwaarde van de GNU GPL-licentie is dat je de broncode van de applicatie deelt
wanneer je wijzigingen of toevoegingen maakt op basis van deze applicatie.
Zie het bestand LICENSE.txt voor de volledige versie van deze licentie.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Contact
=======

Voor vragen of opmerkingen:

Geert Wirken  
info@rijdendetreinen.nl  
http://www.rijdendetreinen.nl/  
http://twitter.com/djiwie