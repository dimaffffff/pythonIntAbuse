CODES = [
"OUT", "HALT", "ALLOC", "SET", "JUMP", "EQUAL", "NOT", "IF", "ADD", "FREE", "DUMP", "PRINTSTR", "LESS", "INPUT", "STRTOINT", "TRACE", "RETURN", "AND", 
"MULT", "COMMENT", "VAR", "FVAR", "LIST", "APPEND", "POP", "INTTOSTR", "CONC"
]
#small test
CODE = """
TRACE
JUMP .allocateBasics !1

VAR #duration

TRACE
JUMP .getDuration !1

SET *duration ret
MULT duration !60 *duration

SET *arg1 duration
LIST #songs
TRACE
JUMP .getSongAmount !1

VAR #songCount
VAR #totalSongs
SET *songCount ret2

HALT
.getSongAmount
VAR #songCounter
VAR #total
VAR #loopCond
VAR #songDur

.songLoop
INPUT " enter duration of a song in seconds > " *songDur
STRTOINT songDur *songDur
ADD songDur total *total
ADD songCounter !1 *songCounter
COMMENT " 'songs' is basically a global here cuz I am lazy "
APPEND songDur *songs 
LESS total arg1 *loopCond
JUMP .songLoop loopCond

PRINTSTR " You have entered enough songs "
SET *ret total
COMMENT " arg2 is used as a second return value here "
SET *ret2 songCounter

FVAR #total
FVAR #loopCond
FVAR #songDur
FVAR #songCounter
RETURN

.allocateBasics
VAR #tmp 
VAR #arg1 
VAR #arg2
VAR #ret
VAR #ret2

RETURN

.getDuration
VAR #tmpDur 
VAR #tmpInvalid 
VAR #condMin 
VAR #condMax

.durLoopStart
INPUT " What is the duration of the training session? > " *tmp
STRTOINT tmp *tmpDur

LESS !9 tmpDur *condMin
LESS tmpDur !31 *condMax
AND condMin condMax *tmpInvalid
NOT tmpInvalid *tmpInvalid

JUMP .invalidDur tmpInvalid

SET *ret tmpDur

FVAR #tmpDur 
FVAR #tmpInvalid 
FVAR #condMin 
FVAR #condMax

RETURN
.invalidDur
PRINTSTR " Invalid session duration (must be 10-30 mins) "
JUMP .durLoopStart !1
"""

CALL_BUFFER_SIZE = 16
START_OFFSET = 3
MAX_ARGS = 3
ARG_MEM = 2
INSTRUCTION_MEM = MAX_ARGS * ARG_MEM + 1
PART_SIZE = 16
PART_AMOUNT = 4096
DEBUGMODE = False
INTERPRETER_DEBUG = False
COREDUMP_ON_EXIT = False
PRINT_VARTABLE_NAVIGATION = False
world:int = 0

def printv(msg:str):
    if PRINT_VARTABLE_NAVIGATION:
        print(msg)

def printi(msg:str):
    if INTERPRETER_DEBUG:
        print(msg)

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
            print(f"#{partIndex}: {part} ",end="")
        partIndex += 1
    print()


def PANIC(msg:str,error:str):
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

def initList(item:int) -> int: #linked list to be exact
    mem = alloc(2)
    writePack(mem,[item,0]) #null pointer is the list's terminator
    return mem

def getItemList(list:int,index:int) -> int:
    item = list 
    count = 0
    while True:
        nextItem = readPart(item+1)
        if count == index:
            break
        elif nextItem == 0:
            if index != -1:
                PANIC(f"Tried to access index {index} but the list (in partition {list}) is not big enough","out of bounds")
            break 
        count += 1
        item = nextItem
    return item

def appendList(list:int,item:int):
    newItem = initList(item)
    lastItem = getItemList(list,-1)
    writePart(lastItem+1,newItem)

#Pops the index ONE in the list
def popList(list:int)->int:
    lastItem = getItemList(list,-1)
    if lastItem == list:
        PANIC("Attempted to pop an item of an empty list","out of bounds")
    poppedItem = getItemList(list,1)
    if lastItem != poppedItem:
        nextItem = getItemList(list,2)
    else:
        nextItem = 0
    writePart(list+1,nextItem)
    return poppedItem

#The actual interpreter and parser

#Parser

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
    writePart(instructionStart + 1,0) #Write the ic into reserved index 1
    callBuffer = alloc(CALL_BUFFER_SIZE+1)
    writePart(instructionStart + 2,callBuffer) #Write the call buffer pointer into index 2
    writePart(callBuffer,0) #Set the current buffer size to 0
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
            printv(f"{argVal} is {(len(varTable) - 1)}")
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

        printi(f"ic is {ic}, opcode is {code}, args are {args}")
        
        execHandle(code,args)
        if readPart(instructions+1) == ic: #check if the instruction modified the ic
            writePart(instructions+1,ic+1)

def execHandle(opcode:int,args:list[int]):
    code = CODES[opcode]
    printi(f"executing {code} with arguments: {args}")

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

def h_VAR(args:list[int]):
    h_ALLOC([args[0],1])

def h_FVAR(args:list[int]):
    h_FREE([args[0],1])

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
    h_SET([args[2],args[0] < args[1]])

def h_PRINTSTR(args: list[int]):
    print(readStr(args[0]))

def h_INPUT(args: list[int]):
    usrInput = input(readStr(args[0]))
    strmem = alloc(len(usrInput) + 1)
    writeStr(strmem,usrInput)
    h_SET([args[1],strmem])
    
def h_TRACE(args: list[int]):
    prog = readPart(0)
    buffer = readPart(prog+2)
    newElement = readPart(buffer) + 1
    ic = readPart(prog+1)
    writePart(newElement+buffer,ic)
    writePart(buffer,newElement)

def h_RETURN(args: list[int]):
    prog = readPart(0)
    buffer = readPart(prog+2)
    lastElement = readPart(buffer)
    if lastElement == 0:
        PANIC("Tried to RETURN, but the call buffer is empty!","invalid use")
    ic = readPart(buffer+lastElement) + 2 #skip the TRACE and the next instruction for funsies
    writePart(prog+1,ic)
    writePart(buffer,lastElement-1)

def h_STRTOINT(args: list[int]):
    string = readStr(args[0])
    if len(string) > 0:
        converted = int(string)
    else:
        converted = 0 #this treats empty strings as 0
    h_SET([args[1],converted])

def h_AND(args: list[int]):
    h_SET([args[2],args[0] and args[1]])

def h_MULT(args:list[int]):
    h_SET([args[2],args[0] * args[1]])

def h_COMMENT(args:list[int]):
    pass

def h_LIST(args:list[int]):
    writePart(args[0],initList(0))

def h_APPEND(args:list[int]):
    appendList(args[1],args[0])

def h_POP(args:list[int]):
    item = readPart(popList(args[0]))
    h_SET([args[1], item])



if checkAlloc(0):
    free(0,1)

writePart(alloc(1),parse(CODE))#This SHOULD reserve the first partition for the pointer to prog (crappy code but I am out of ideas)

startProg(readPart(0))

