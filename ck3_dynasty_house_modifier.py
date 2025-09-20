
import os.path
import glob
import datetime
import os
import shutil
from collections import defaultdict


#Set this to the root directory of the game files you want to parse
gameRoot = r'C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game'

#Set this to the root directory of the history character files you want to parse,
#I usually set this to a staging directory where I have manually edited files
staging = r'C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\game'
modDir = 'dyn_mod'



LATEST_START_DATE = datetime.date(1178, 10, 1)

DELIMS = [None, '{', '}', '=']

def stripComments(line):
    found = line.find('#')

    if found != -1:
        line = line[:found]
        
    return line.strip()

def createDate(dateStr):
    if isinstance(dateStr, datetime.date):
        return dateStr

    dateEntries = dateStr.split('.')[:3]

    dateNums = [int(x) if x else 1 for x in dateEntries]

    while len(dateNums) < 3:
        dateNums.append(1)

    try:
        dateObj = datetime.date(*dateNums)
    except ValueError:
        dateNums[-1] = 1
        dateObj = datetime.date(*dateNums)

    return dateObj

def tokenizer(textFile):

    for line in textFile:
        stripped = stripComments(line)

        firstIndex = stripped.find('"')

        while firstIndex >= 0:
            if firstIndex > 0:
                yield from seperateTokens(stripped[:firstIndex].strip(), DELIMS)

            secondIndex = stripped.find('"', firstIndex+1)

            if secondIndex < 0:
                stripped = stripped[firstIndex+1:].strip()
            else:
                yield stripped[firstIndex+1:secondIndex]
                stripped = stripped[secondIndex+1:].strip()
                firstIndex = stripped.find('"')

        yield from seperateTokens(stripped, DELIMS)



def seperateTokens(string, delimiters):

    if len(string) < 1:
        return

    if not delimiters:
        yield string
        return

    tokens = string.split(delimiters[0])

    yield from seperateTokens(tokens[0], delimiters[1:])

    for token in tokens[1:]:

        if delimiters[0]:
            yield delimiters[0]

        yield from seperateTokens(token, delimiters[1:])



def createNameValues(tokenIter):
    nameValues = []
    token = next(tokenIter, None)

    while token is not None and token != '}':

        if token == '{':
            nameValues.append((None, createNameValues(tokenIter)))
            token = next(tokenIter, None)
            continue

        nextToken = next(tokenIter, None)

        if nextToken != '=':
            nameValues.append((None, token))
            token = nextToken
        else:
            nextToken = next(tokenIter, None)

            if nextToken != '{':
                nameValues.append((token, nextToken))
            else:
                nameValues.append((token, createNameValues(tokenIter)))


            token = next(tokenIter, None)

    return nameValues


def parseFile(fileName):
    with open(fileName, encoding='utf_8_sig') as textFile:
        tokens = tokenizer(textFile)
        tokenIter = iter(tokens)
        return list(createNameValues(tokenIter))

class Dynasty:
    def __init__(self, ident):
        self.name = ''
        self.ident = ident
        self.prefix = ''
        self.culture = ''
        self.motto = ''
        self.forced_coa_religiongroup = ''
        self.parentDynasty = None
        self.founder = None
        self.members = set()
        self.houses = set()
        self.childDynasties = set()
        self.foundedOn = None
        self.duplicate = False
        self.dupChildren = set()

class House:
    def __init__(self, ident):
        self.name = ''
        self.ident = ident
        self.prefix = ''
        self.culture = ''
        self.motto = ''
        self.forced_coa_religiongroup = ''
        self.recordedDynasty = None
        self.parentDynasty = None
        self.founder = None
        self.members = set()
        self.childDynasties = set()
        self.foundedOn = None
        self.duplicate = False
        self.dupChildren = set()

class Character:
    def __init__(self, ident):
        self.name = ''
        self.ident = ident
        self.dynasty = None
        self.foundedDynasty = None
        self.father = None
        self.mother = None
        self.born = None
        self.bastard = False
        self.matWives = set()
        self.dParent = None
        self.dChildren = set()
        self.newDynasty = None
        self.newFoundedDynasty = None
        self.religion = ''
        self.culture = ''
        self.isFounder = False

def getDynasties():
    dynData1 = parseFile(os.path.join(gameRoot, 'common', 'dynasties', '00_dynasties.txt'))
    dynData2 = parseFile(os.path.join(gameRoot, 'common', 'dynasties', '03_fp2_dynasties.txt'))
    dynData3 = parseFile(os.path.join(gameRoot, 'common', 'dynasties', '01_vanity_dynasties.txt'))

    dynasties = {}

    for dynData in [dynData1, dynData2, dynData3]:

        for dynNum, dynProps in dynData:
            if not isinstance(dynProps, list):
                continue
            current = Dynasty(dynNum)

            for name, value in dynProps:
                if name == 'name':
                    current.name = value
                elif name == 'prefix':
                    current.prefix = value
                elif name == 'culture':
                    current.culture = value
                elif name == 'motto':
                    current.motto = value
                elif name == 'forced_coa_religiongroup':
                    current.forced_coa_religiongroup = value

            dynasties[dynNum] = current


    return dynasties


def getHouses(dyns):
    houseData1 = parseFile(os.path.join(gameRoot, 'common', 'dynasty_houses', '00_dynasty_houses.txt'))
    houseData2 = parseFile(os.path.join(gameRoot, 'common', 'dynasty_houses', 'ep3_dynasty_houses.txt'))

    houses = {}

    for houseData in [houseData1, houseData2]:

        for houseID, houseProps in houseData:
            if not isinstance(houseProps, list):
                continue

            current = House(houseID)

            for name, value in houseProps:
                if name == 'name':
                    current.name = value
                elif name == 'prefix':
                    current.prefix = value
                elif name == 'motto':
                    current.motto = value
                elif name == 'dynasty':
                    try:
                        current.recordedDynasty = dyns[value]
                        current.recordedDynasty.houses.add(current)
                        current.culture = current.recordedDynasty.culture
                        current.forced_coa_religiongroup = current.recordedDynasty.forced_coa_religiongroup
                    except KeyError:
                        pass
                    

            houses[houseID] = current

            
        


    return houses

def getCharacters(dyns, houses):
    characters = {}
    
    for charFile in glob.glob(os.path.join(staging, 'history', 'characters', '*.txt')):
        charData = parseFile(charFile)

        for charID, charProps in charData:
            if not isinstance(charProps, list):
                continue

            current = Character(charID)

            for name, value in charProps:
                if name == 'name':
                    current.name = value
                elif name == 'dynasty':
                    try:
                        current.dynasty = dyns[value]
                        current.dynasty.members.add(current)
                    except KeyError:
                        pass
                elif name == 'dynasty_house':
                    try:
                        current.dynasty = houses[value]
                        current.dynasty.members.add(current)
                    except KeyError:
                        pass
                elif name == 'father':
                    current.father = value
                elif name == 'mother':
                    current.mother = value
                elif name == 'culture':
                    current.culture = value
                elif name == 'religion':
                    current.religion = value
                elif name == 'trait':
                    if value == 'bastard' or value == 'bastard_founder':
                        current.bastard = True
                    elif value == 'legitimized_bastard':
                        current.bastard = False
                elif name[0].isnumeric():
                    for subName, subValue in value:
                        if subName == 'birth':
                            current.born = createDate(name)
                        elif subName == 'add_matrilineal_spouse':
                            current.matWives.add(subValue)
                        elif subName == 'dynasty':
                            current.foundedDynasty = dyns[subValue]
                            current.foundedDynasty.members.add(current)
                            
                            currentDate = createDate(name)
                            if current.foundedDynasty.foundedOn:
                                if currentDate < current.foundedDynasty.foundedOn:
                                    current.foundedDynasty.foundedOn = currentDate
                            else:
                                current.foundedDynasty.foundedOn = currentDate

                        elif subName == 'dynasty_house':
                            current.foundedDynasty = houses[subValue]
                            current.foundedDynasty.members.add(current)

                            currentDate = createDate(name)
                            if current.foundedDynasty.foundedOn:
                                if currentDate < current.foundedDynasty.foundedOn:
                                    current.foundedDynasty.foundedOn = currentDate
                            else:
                                current.foundedDynasty.foundedOn = currentDate
                        elif subName == 'father':
                            current.father = subValue
                        elif subName == 'culture':
                            current.culture = subValue
                        elif subName == 'religion':
                            current.religion = subValue
                        elif subName == 'trait':
                            if subValue == 'bastard':
                                current.bastard = True
                            elif subValue == 'legitimized_bastard':
                                current.bastard = False
                        elif subName == 'remove_trait':
                            if subValue == 'bastard':
                                current.bastard = False
                            

            characters[charID] = current

    setFounders(dyns, houses)

    setParents(characters)

    setParentDynasties(dyns, houses)

    return characters


def setParents(chars):
    for char in chars.values():
        if char.father:
            try:
                char.father = chars[char.father]
            except KeyError:
                char.father = None
        if char.mother:
            try:
                char.mother = chars[char.mother]
            except KeyError:
                char.mother = None
        matWives = set()
        for wife in char.matWives:
            try:
                matWives.add(chars[wife])
            except KeyError:
                pass
        char.matWives = matWives

    for char in chars.values():
        if not char.bastard:
            father = char.father
            mother = char.mother

            if not father:
                continue

            if mother in father.matWives or (mother and (mother.dynasty or mother.foundedDynasty) and father.bastard and (not father.isFounder)):
                if mother and (mother.dynasty or mother.foundedDynasty):
                    char.dParent = mother
                    mother.dChildren.add(char)
            else:
                if father.dynasty or father.foundedDynasty:
                    char.dParent = father
                    father.dChildren.add(char)

def setFounders(dyns, houses):
    combined = dyns.copy()
    combined.update(houses)
    
    for dyn in combined.values():
        dyn.founder = min(dyn.members, key=lambda x: x.born, default=None)
        if dyn.founder:

            dyn.founder.isFounder = True

            if dyn.foundedOn:
                if dyn.founder.foundedDynasty != dyn:
                    dyn.foundedOn = dyn.founder.born
            else:
                dyn.foundedOn = dyn.founder.born


def setParentDynasties(dyns, houses):
    combined = dyns.copy()
    combined.update(houses)
    
    for dyn in combined.values():
        founder = dyn.founder

        if founder and founder.dParent:
            pDyn = founder.dParent.foundedDynasty

            if not pDyn:
                pDyn = founder.dParent.dynasty

            if pDyn and pDyn != dyn:
                dyn.parentDynasty = pDyn
                pDyn.childDynasties.add(dyn)
                if dyn.name == pDyn.name:
                    dyn.duplicate = True
                    pDyn.dupChildren.add(dyn)


def getTrueDynasty(dyn):
    if dyn.parentDynasty:
        return getTrueDynasty(dyn.parentDynasty)
    else:
        return dyn

def convertHouseToDynasty(house):
    dynIdent = 'dynasty_dhc_%s' % house.ident[6:]

    newDyn = Dynasty(dynIdent)
    newDyn.name = house.name
    if not newDyn.name.startswith('dynn_'):
        newDyn.name = 'dynn_' + newDyn.name
    newDyn.prefix = house.prefix
    newDyn.motto = house.motto
    newDyn.culture = house.founder.culture
    newDyn.forced_coa_relgiongroup = house.forced_coa_religiongroup
    newDyn.foundedOn = house.foundedOn

    return newDyn

def getDynastiesToConvert(dyns, houses):
    convertDyns = {}
    newDyns = {}
    modifiedHouses = set()

    for house in houses.values():
        if house.foundedOn and house.foundedOn <= LATEST_START_DATE:
            if not house.parentDynasty:

                newDyn = convertHouseToDynasty(house)
                newDyns[house] = newDyn
                house.parentDynasty = newDyn
                house.duplicate = True
                convertDyns[house] = newDyn
                for dup in house.dupChildren:
                    convertDyns[dup] = newDyn



    for dyn in dyns.values():
        if dyn.foundedOn and dyn.foundedOn <= LATEST_START_DATE:

            if not dyn.duplicate:
                if dyn.parentDynasty:

                    houseIdent = 'house_dhc_%s' % dyn.ident

                    newHouse = House(houseIdent)
                    newHouse.name = dyn.name
                    if not newHouse.name.startswith('dynn_'):
                        newHouse.name = 'dynn_' + newHouse.name
                    newHouse.prefix = dyn.prefix
                    newHouse.culture = dyn.culture
                    newHouse.motto = dyn.motto
                    newHouse.forced_coa_relgiongroup = dyn.forced_coa_religiongroup
                    newHouse.parentDynasty = dyn.parentDynasty
                    newHouse.foundedOn = dyn.foundedOn
                    
                    convertDyns[dyn] = newHouse
                    newDyns[dyn] = newHouse
                    for dup in dyn.dupChildren:
                        convertDyns[dup] = newHouse
                else:
                    for dup in dyn.dupChildren:
                        convertDyns[dup] = dyn


    for house in houses.values():
        if house.foundedOn and house.foundedOn <= LATEST_START_DATE:

            if not house.duplicate:
                trueDyn = getTrueDynasty(house)

                if trueDyn != house.recordedDynasty:
                    modifiedHouses.add(house)

                for dup in house.dupChildren:
                    convertDyns[dup] = house

                

    return newDyns, convertDyns, modifiedHouses

def getCharactersToConvert(chars, convertDyns):
    convertChars = {}
    for char in chars.values():
        if char.born <= LATEST_START_DATE:
            dyn = char.dynasty
            fDyn = char.foundedDynasty

            if dyn in convertDyns:
                dynConversion = convertDyns[dyn]
            else:
                dynConversion = None

            if fDyn in convertDyns:
                fDynConversion = convertDyns[fDyn]
            else:
                fDynConversion = None

            if dynConversion or fDynConversion:
                convertChars[char.ident] = (dynConversion, fDynConversion)

    return convertChars

dynProps = ['name', 'prefix', 'motto', 'culture', 'forced_coa_religiongroup']
houseProps = ['name', 'prefix', 'motto']

def createDynastiesFiles(newDyns, modifiedHouses):
    dynastyDir = os.path.join(modDir, 'common', 'dynasties')
    os.makedirs(dynastyDir, exist_ok=True)
    houseDir = os.path.join(modDir, 'common', 'dynasty_houses')
    os.makedirs(houseDir, exist_ok=True)
    
    with open(os.path.join(dynastyDir, 'zzz_99_dhc_dynasties.txt'), 'w', encoding='utf_8_sig') as dynFile:
        with open(os.path.join(houseDir, 'zzz_99_dhc_dynasty_houses.txt'), 'w', encoding='utf_8_sig') as houseFile:

            dynsToWrite = modifiedHouses.union(newDyns.values())
            
            for dyn in sorted(dynsToWrite, key = lambda x: (x.foundedOn, x.ident)):

                if isinstance(dyn, Dynasty):
                    fileToWrite = dynFile
                    propsToWrite = dynProps
                else:
                    fileToWrite = houseFile
                    propsToWrite = houseProps
                

                fileToWrite.write('%s = {\n' % dyn.ident)

                for prop in propsToWrite:
                    propVal = getattr(dyn, prop)
                    if propVal:
                        fileToWrite.write('    %s = "%s"\n' % (prop, propVal))

                if isinstance(dyn, House):
                    fileToWrite.write('    dynasty = %s\n' % getTrueDynasty(dyn).ident)

                fileToWrite.write('}\n\n')
            

def createCharFiles(convertChars):
    charDir = os.path.join(modDir, 'history', 'characters')
    os.makedirs(charDir, exist_ok=True)
    for charPath in glob.glob(os.path.join(staging, 'history', 'characters', '*.txt')):
        newCharFilePath = os.path.join(charDir, os.path.split(charPath)[1])
        with open(charPath, encoding='utf_8_sig') as charInFile:
            with open(newCharFilePath, 'w', encoding='utf_8_sig') as charOutFile:
                modified = processCharFile(convertChars, charInFile, charOutFile)

        if not modified:
            os.remove(newCharFilePath)

def createCOAFile(newDyns):
    coaDir = os.path.join(modDir, 'common', 'coat_of_arms', 'coat_of_arms')
    os.makedirs(coaDir, exist_ok=True)

    with open(os.path.join(coaDir, 'zzz_dhc_dynasties.txt'), 'w', encoding='utf_8_sig') as coaFile:

        for oldDyn in sorted(newDyns.keys(), key = lambda x: x.ident):
            newDyn = newDyns[oldDyn]
            coaFile.write('%s = %s\n\n' % (newDyn.ident, oldDyn.ident))




def processCharFile(convertChars, inFile, outFile):
    textIter = iter(inFile)
    modified = False

    try:
        while True:
            currentLine = next(textIter)
            outFile.write(currentLine)

            currentLine = stripComments(currentLine)

            if '{' in currentLine:
                currentChar = currentLine.split()[0]
                newHouses = convertChars.get(currentChar, (None, None))
                if any(newHouses):
                    modified = True

                nextLine = printNextLine(newHouses, textIter, outFile, 1)
                processChar(newHouses, nextLine, textIter, outFile, 1)
                
    except StopIteration:
        pass

    return modified

def printNextLine(houses, textIter, outFile, level):
    if level == 1:
        dynasty = houses[0]
    elif level == 2:
        dynasty = houses[1]
    else:
        dynasty = None

    dynIndex = -1
    
    nextLine = next(textIter)
    if dynasty:
        lineTokens = stripComments(nextLine).replace('=', ' = ').split()

        if 'dynasty' in lineTokens:
            dynIndex = lineTokens.index('dynasty')
        elif 'dynasty_house' in lineTokens:
            dynIndex = lineTokens.index('dynasty_house')

        if dynIndex > -1:

            if isinstance(dynasty, Dynasty):
                lineTokens[dynIndex] = 'dynasty'
            else:
                lineTokens[dynIndex] = 'dynasty_house'

            lineTokens[dynIndex+2] = dynasty.ident

            nextLine = '    %s\n' % ' '.join(lineTokens)

    outFile.write(nextLine)
    return stripComments(nextLine)


def processChar(houses, line, textIter, outFile, level):
    while True:
        beginPos = line.find('{')
        endPos = line.find('}')

        bothExist = beginPos >= 0 and endPos >= 0

        if (not bothExist and beginPos >= 0) or (bothExist and beginPos < endPos):
            line = processChar(houses, line[beginPos+1:], textIter, outFile, level + 1)
        elif endPos >= 0:
            return line[endPos+1:]
        else:
            line = printNextLine(houses, textIter, outFile, level)


def generateShortReport(newDyns, modifiedHouses):
    newDynasties = set()
    justNew = set()
    newHousesForDynasty = defaultdict(set)
    for oldDyn, newDyn in newDyns.items():
        if isinstance(newDyn, Dynasty):
            newDynasties.add((oldDyn, newDyn))
            justNew.add(newDyn)

        else:        
            newHousesForDynasty[getTrueDynasty(newDyn)].add((newDyn, False))

    for dyn in modifiedHouses:
        newHousesForDynasty[getTrueDynasty(dyn)].add((dyn, False))

    with open(os.path.join(gameRoot, 'localization', 'english', 'dynasties', 'dynasty_names_l_english.yml'), encoding='utf_8_sig') as localFile:
        dynNames = {}
        
        for line in localFile:
            line = line.strip()
            if not line.startswith('#'):
                tokens = []
                for x in line.split(':'):
                    stripped = x.strip('" 01')
                    if stripped:
                        tokens.append(stripped)

                if len(tokens) == 2:
                    dynNames[tokens[0]] = tokens[1]

    cultureNames = {}

    with open(os.path.join(gameRoot, 'localization', 'english', 'culture', 'cultures_l_english.yml'), encoding='utf_8_sig') as localFile:
        
        for line in localFile:
            line = line.strip()
            if not line.startswith('#'):
                tokens = []
                for x in line.split(':'):
                    stripped = x.strip('" 01')
                    if stripped:
                        tokens.append(stripped)

                if len(tokens) == 2:
                    cultureNames[tokens[0]] = tokens[1]
            
        
    with open(os.path.join(modDir, 'short_house_conversion_report.txt'), 'w', encoding='utf_8_sig') as reportFile:
        reportFile.write('New Dynasties:\n\n')
        for oldDyn, newDyn in sorted(newDynasties, key = lambda x: (x[1].foundedOn, x[1].ident)):

            if not oldDyn.recordedDynasty:
                oldDynName = "[MISSING]"
            else:
                oldDynName = oldDyn.recordedDynasty.name

            try:
                reportFile.write('%s, previously house of %s\n' % (dynNames[newDyn.name], dynNames[oldDynName]))
            except Exception:
                print(oldDyn.ident, newDyn.ident)
                raise

            if newHousesForDynasty[newDyn]:

                houseNames = []

                for dyn, newCOA in sorted(newHousesForDynasty[newDyn], key = lambda x: (x[0].foundedOn, x[0].ident)):

                    houseNames.append(dynNames[dyn.name])


                reportFile.write('    Houses: %s\n' % ', '.join(houseNames))
                
            reportFile.write('\n')

        reportFile.write('\nExisting Dynasties with new houses:\n\n')

        for dyn, houses in sorted(newHousesForDynasty.items(), key = lambda x: (x[0].foundedOn, x[0].ident)):
            if dyn not in justNew:

                houseNames = []
                for house, newCOA in sorted(houses, key = lambda x: (x[0].foundedOn, x[0].ident)):
                    houseNames.append(dynNames[house.name])

                reportFile.write('%s: %s\n\n' % (dynNames[dyn.name], ', '.join(houseNames)))


if __name__ == "__main__":

    dyns = getDynasties()
    houses = getHouses(dyns)
    chars = getCharacters(dyns, houses)

    both = dyns.copy()
    both.update(houses)


    newDyns, convertDyns, modifiedHouses = getDynastiesToConvert(dyns, houses)

    convertChars = getCharactersToConvert(chars, convertDyns)

    generateShortReport(newDyns, modifiedHouses)

    shutil.rmtree(os.path.join(modDir, 'common'), ignore_errors=True)
    shutil.rmtree(os.path.join(modDir, 'history'), ignore_errors=True)

    createDynastiesFiles(newDyns, modifiedHouses)
    createCOAFile(newDyns)
    createCharFiles(convertChars)

