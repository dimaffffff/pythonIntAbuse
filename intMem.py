CODES = [
"OUT", "HALT", "ALLOC", "SET", "JUMP", "EQUAL", "NOT", "IF", "ADD", "FREE", "DUMP", "PRINTSTR", "LESS"
]
#small test
CODE = """
ALLOC #running !1
ALLOC #counter !1

.start

PRINTSTR " hello world "
ADD counter !1 *counter
EQUAL counter !5 *running 
NOT running *running

JUMP .start running

HALT
"""

START_OFFSET = 2
MAX_ARGS = 3
ARG_MEM = 2
INSTRUCTION_MEM = MAX_ARGS * ARG_MEM + 1
PART_SIZE = 16
PART_AMOUNT = 256
DEBUGMODE = False
COREDUMP_ON_EXIT = False
world:int = 0

def printd(msg:str,mods:list[str] = []):
    if DEBUGMODE:
        if "NOEND" in mods:
            print(msg,end="")
        else:
            print(msg)

def DUMPCORE():
    print("The atable is: ")
    mask = ~((~0) << PART_AMOUNT)
    atable = world & mask 
    print(f"{atable:b}")
    partIndex = 0 
    while partIndex < PART_AMOUNT:
        if (world >> partIndex) & 1:
            mask = ~((~0) << PART_SIZE)
            part = (world >> (PART_AMOUNT + PART_SIZE * partIndex)) & mask 
            print(f"PARTITION #{partIndex} ({part}): {part:b}")
        partIndex += 1


def PANIC(msg:str,error:str):
    print(f"{world:b}")
    print("CORE DUMP: ")
    DUMPCORE()
    print("")
    print(msg)
    print(f"!!! {error.upper()} !!!")
    exit()

def alloc(amount:int) -> int:
    global world
    printd(f"can we allocate {amount} partitions... ",["NOEND"])
    inrow = 0
    index = 0 
    amount = max(amount,1)

    for i in range(PART_AMOUNT):
        if inrow == amount:
            break 
        if not ((world >> i) & 1):
            inrow += 1
        else:
            inrow = 0
        index = i - inrow + 1

    if inrow != amount:
        printd("no")
        PANIC(f"Tried to allocate {amount} partitions but the allocator couldn't find enough free partitions", "out of memory")

    if amount != 0:
        mask = (~(~0 << inrow)) << index
        world |= mask
    printd(f"yes, to {index}")
    return index

def free(index:int,amount:int):
    global world
    end = index+amount-1
    printd(f"can we free partitions {index}-{end}... ",["NOEND"])
    for i in range(amount):
        offset = i + index
        if not checkAlloc(offset):
            printd("no")
            PANIC(f"tried to free partitions {index}-{end} but partition {offset} is not allocated", "double free")
        else:
            writePart(offset,0)#in real world free() wouldn't clear the data but I don't want any unpredictable behaviour

    mask = ~(~((~0) << amount) << index)
    world &= mask
    printd("yes")

def checkAlloc(index:int):
    if index < PART_AMOUNT and index >= 0:
        return bool((world >> index) & 1) 
    else:
        return False

def sizeof(number:int):
    return number.bit_length()

def writePart(index:int,number:int): 
    printd(f"can we write {number} into partition {index}... ",["NOEND"])
    global world
    size = sizeof(number)
    if size > PART_SIZE: #in real world this usually wouldn't segfault but I don't want any silent memory corruption
        printd("no")
        PANIC(f"Tried to write {size} bits into a partition but the partition size is {PART_SIZE}","segmentation fault")

    if number < 0:
        printd("no")
        PANIC(f"Tried to write {number} into partition {index} but it is negative", "invalid argument")

    if not checkAlloc(index):
        printd("no")
        PANIC(f"Tried to write to partition {index} but it is unallocated","segmentation fault")

    bitIndex = index * (PART_SIZE)
    bitIndex += PART_AMOUNT
    mask = ~(~0 << PART_SIZE)
    mask = mask << bitIndex 
    world &= (~mask)
    mask = number
    mask = mask << bitIndex
    world |= mask
    printd("yes")

def readPart(index:int):
    printd(f"can we read partition {index}... ", ["NOEND"])
    if not checkAlloc(index):
        printd("no")
        PANIC(f"Tried to read partition {index} but it is unallocated","segmentation fault")
    mask = ~(~0 << PART_SIZE)
    value = (world >> (PART_SIZE * index) + PART_AMOUNT) & mask
    printd(f"yes, it is {value}")
    return value

def writePack(index: int,numbers: list[int]):
    printd(f"writing {numbers} into {index}")
    for i in range(len(numbers)):
        writePart(index + i,numbers[i])

def writeStr(index:int,string:str):
    pack: list[int] = [len(string)]
    for i in string:
        pack.append(ord(i))
    writePack(index,pack)

def readStr(index:int) -> str:
    strLen = readPart(index)
    charPtr = index + 1
    charList: list[str] = []
    while charPtr - index < strLen + 1:
        charList.append(chr(readPart(charPtr)))
        charPtr += 1
    return "".join(charList)

#The actual interpreter and parser

#Parser
#DOES NOT HANDLE STRING LITERALS AS A PROOF OF CONCEPT

#MUTATES code
def getTags(code:list[str]):    
    tags: dict[str,int] = {}
    i = 0

    while i < len(code):
        printd(f"on line {i}")
        if len(code[i]) > 0:
            if code[i][0] == ".":
                tags[code.pop(i)[1:]] = i
            else:
                i += 1
        else:
            _ = code.pop(i)
 
    return code,tags

#MUTATES sLine
def handleStrings(sLine:list[str]):
    inStr = False
    stringList:list[str] = []
    i = 0
    while i < len(sLine):
        if sLine[i] == "\"":
            inStr = not inStr
            _= sLine.pop(i)
            if not inStr:
                string = " ".join(stringList)
                strmem = alloc(len(string)+1) #Every string allocates memory, possibly leaking it, problems?
                sLine.insert(i,f"!{strmem}")
                writeStr(strmem,string)
                stringList.clear()
            else:
                i -= 1
        else:
            if inStr:
                stringList.append(sLine.pop(i))
                i -= 1
        i += 1


 
#This will write the code into any space given by the alloc() function
def parse(code:str) -> int:
    printd("---  PARSING ---")
    memoryNeeded = INSTRUCTION_MEM * 2 #Memory needed for the program's code if we are being exact

    codeLines = code.splitlines()
    codeLines, tags = getTags(codeLines)
    printd(f"{codeLines}")
    printd(f"{tags}")
    
    memoryNeeded += len(codeLines) * INSTRUCTION_MEM
    #WRITE THE INSTRUCTIONS INTO THE MEMORY
    variables: list[str] = []
    instructionStart = alloc(memoryNeeded + START_OFFSET) 
    instructionPointer = instructionStart + START_OFFSET
    writePart(instructionPointer - (START_OFFSET - 1),0) #Write the ic into reserved index 1
    for i in codeLines:
        if len(i) != 0:
            printd(f"Trying to parse {i}")
            splited = i.split()
            printd(f"Split it into {splited}")
            handleStrings(splited)
            opcode = getInstructionCode(splited[0])
            printd(f"And get the opcode - {opcode}")
            args: list[int] = []

            for j in splited[1:]:
                processedArg = processArg(j,variables,tags)
                args.extend(processedArg)
                printd(f"We get {processedArg} as our argument")


            pack = [opcode]
            pack.extend(args)
            writePack(instructionPointer,pack)
            instructionPointer += INSTRUCTION_MEM

    #ALLOCATE THE VARIABLE ARRAY
    varArray= alloc(len(variables))
    writePart(instructionStart,varArray)
    return instructionStart

#MUTATES THE VAR TABLE, does not handle string literals for now
def processArg(arg:str,varTable:list[str],tags:dict[str,int]) -> list[int]:
    argType = 0
    argVal = arg[1:]
    match arg[0]:
        case "!":
            argType = 1 #Treat this argument literally
        case "*":
            argType = 2 #What is the location of this variable?
        case "#":
            argType = 0 #What is the location of the pointer?
        case ".":
            argType = 4 #Replace its value with a tag and switch type to 1
        case _:
            argVal = arg
            argType = 3 #What is the value of this variable?

    if argType == 1:
        argVal = int(argVal)
    elif argType == 4:
        if argVal not in tags.keys():
            PANIC(f"tag {argVal} does not exist","parser error")
        argVal = tags[argVal]
        argType = 1
    else:
        if argVal not in varTable:
            varTable.append(argVal)
            printd(f"Appended {argVal} to varTable!")
        argVal = varTable.index(argVal)
    return [argType,argVal]

def getInstructionCode(instruction: str) -> int:
    if instruction in CODES:
        return CODES.index(instruction)
    else:
        PANIC(f"{instruction} is not a valid instruction","invalid instruction")
        return int(-3e1000)#just so my lsp shuts up

#Interpreter
def startProg(instructions:int):
    printd("--- INTERPRETER ---")
    while True:
        ic = readPart(instructions + 1)
        start = instructions + START_OFFSET + ic * INSTRUCTION_MEM
        code = readPart(start)
        args: list[int] = []
        for i in range(MAX_ARGS):
            arg: list[int] = []
            for j in range(2):
                
                argPtr = start + 1 + i * 2 + j
                arg.append(readPart(argPtr))
                printd(f"trying to process: {arg[-1]}")


            args.append(procVar(arg,readPart(instructions)))
            printd(f"and we got: {args[-1]}")
            arg.clear

        printd(f"ic is {ic}, opcode is {code}, args are {args}")
        
        execHandle(code,args)
        if readPart(instructions+1) == ic: #check if the instruction modified the ic
            writePart(instructions+1,ic+1)

def execHandle(opcode:int,args:list[int]):
    code = CODES[opcode]
    printd(f"executing {code} with arguments: {args}")
    func = f"h_{code}"
    if func in globals():
        globals()[func](args)
    else:
        PANIC(f"{code} is not a valid instruction","invalid instruction")

def procVar(var:list[int],varArray:int) -> int:
    if var[0] == 1: #!
        return var[1]
    elif var[0] == 2: #*
        return readPart(var[1] + varArray)
    elif var[0] == 3: # 
        return readPart(readPart(var[1] + varArray))
    else: # #
        return var[1] + varArray

def h_OUT(args: list[int]):
    print(args[0])

def h_HALT(args: list[int]):
    if COREDUMP_ON_EXIT:
        DUMPCORE()
    exit()

def h_ALLOC(args: list[int]):
    varmem = alloc(args[1])
    writePart(args[0],varmem)

def h_SET(args: list[int]):
    if args[0] == 0:
        PANIC("Tried to execute SET but couldn't locate variable","interpreter error")
    writePart(args[0],args[1])

def h_JUMP(args: list[int]):
    if args[1] == 1:
        printd(f"trying to set ic to {args[0]}")
        writePart(1 + readPart(0), args[0])

def h_EQUAL(args: list[int]):
    h_SET([args[2],args[1] == args[0]])

def h_NOT(args: list[int]):
    h_SET([args[1],not args[0]])

def h_IF(args: list[int]):
    if not args[0]:
        ic = readPart(0) + 1
        writePart(ic, readPart(ic) + 2)

def h_ADD(args: list[int]):
    h_SET([args[2],args[1]+args[0]])

def h_FREE(args:list[int]):
    free(readPart(args[0]), args[1])
    writePart(args[0],0)

def h_DUMP(args: list[int]):
    DUMPCORE()

def h_LESS(args: list[int]):
    h_SET([args[2],args[0]<args[1]])

def h_PRINTSTR(args: list[int]):
    print(readStr(args[0]))


if checkAlloc(0):
    free(0,1)

writePart(alloc(1),parse(CODE))#This SHOULD reserve the first partition for the pointer to prog (crappy code but I am out of ideas)

startProg(readPart(0))

