

def evaluate(x):
    return "$"+hex(eval(x.replace("$","0x")))[2:]

print(evaluate("$549F8+$35e"))