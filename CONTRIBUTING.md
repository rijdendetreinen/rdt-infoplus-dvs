Contributing
============

Deze applicatie is ontwikkeld in Python. Verbeteringen of uitbreidingen zijn van harte welkom! Ook meldingen van foute verwerking of ontbrekende functies zijn bijzonder nuttig.

Dit document beschrijft kort wat de beste manier is om mee te helpen in de ontwikkeling van deze applicatie.

Bugs en feature requests melden
-------------------------------

Verzoeken om nieuwe functies, meldingen van bugs, onjuiste dataverwerking of andere problemen, en alle andere meldingen kun je doen in de [issue tracker op GitHub](https://github.com/geertw/rdt-infoplus-dvs/issues). Wanneer je een melding doet van onjuiste dataverwerking helpt het bijzonder wanneer je een (fragment) van de XML-brondata uit InfoPlus toevoegt.

Zelf ontwikkelen
----------------

In GitHub kun je het project forken en zelf de code aanpassen of verbeteren. Aanpassingen, toevoegingen of verbeteringen kun je daarna weer delen door een pull request aan te maken. Zie ook de [documentatie van GitHub](https://help.github.com/articles/using-pull-requests).

Voorbeeldberichten zoals door DVS verspreid worden zijn te vinden in de directory `/testdata/`. Deze kunnen erg nuttig zijn bij het ontwikkelen. Daarnaast is er via het NDOV-loket [documentatie over InfoPlus](https://ndovloket.nl/helpdesk/kb/31/) beschikbaar waarin alle attributen en publicatierichtlijnen beschreven worden.

Let op; alle code komt automatisch onder GNU GPL v3. Ook wanneer je zelf code aanpast of toevoegt die je niet met het hoofdproject deelt ben je volgens de licentie verplicht om de broncode openbaar te maken. Zie ook de [licentie](LICENSE.txt).

Branches
--------

De **master** branch is altijd een production-ready branch. De laatste stable release is een tag op de master branch.

De **develop** branch is de ontwikkelversie. Kleine bugfixes en toevoegingen worden op de develop branch gemaakt.

Grote aanpassingen of toevoegingen kun je het beste op een separate feature branch maken. Mocht er dan nog klein werk nodig zijn voordat de functie ingepast kan worden, dan kan dat op de feature branch gebeuren.

Deze werkwijze is gebaseerd op de uitstekend beschreven [GIT workflow](http://nvie.com/posts/a-successful-git-branching-model/) van Vincent Driessen.