import infoplus_dvs
import glob

xmlFiles = glob.glob('./testdata/*/*.xml') + glob.glob('./testdata/treinlog/*/*.xml')
xmlFiles = sorted(xmlFiles)

for xmlFile in xmlFiles:
	f = open(xmlFile, 'r')
	string = ""
	while 1:
		line = f.readline()
		if not line:break
		string += line

	f.close()

	trein = infoplus_dvs.parse_trein(string)
	print trein