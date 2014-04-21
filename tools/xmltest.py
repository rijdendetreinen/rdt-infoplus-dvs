import infoplus_dvs
import glob
import logging

# Maak output in utf-8 mogelijk in Python 2.x:
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# Stel logger in:
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Laad testdata:
xmlFiles = glob.glob('./testdata/*/*.xml') + glob.glob('./testdata/treinlog/*/*.xml')
xmlFiles = sorted(xmlFiles)

counter = 0

# Doorloop alle testbestanden:
for xmlFile in xmlFiles:
	# Laad bestand in:
	f = open(xmlFile, 'r')
	content = ""

	while True:
		line = f.readline()
		if not line:
			break

		content += line

	f.close()

	# Parse treinbericht:
	trein = infoplus_dvs.parse_trein(content)
	print trein.wijzigingen_str()

	counter = counter + 1

print "%s XML files geparsed" % counter