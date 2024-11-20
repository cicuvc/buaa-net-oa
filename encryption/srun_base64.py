"""SRUN base64 implementation"""

PAD_CHAR = "="
ALPHA = "LVoJPiCN2R8G90yg+hmFHuacZ1OWMnrsSTXkYpUq/3dlbfKwv6xztjI7DeBE45QA"

def getbyte(s, i):
    """Extract byte from string"""
    x = ord(s[i])
    if x > 255:
        print("INVALID_CHARACTER_ERR: DOM Exception 5")
        exit(0)
    return x

def get_base64(s):
    """Calculate base64"""
    i=0
    b10=0
    x = []
    imax = len(s) - len(s) % 3
    if len(s) == 0:
        return s
    for i in range(0,imax,3):
        b10 = (getbyte(s, i) << 16) | (getbyte(s, i + 1) << 8) | getbyte(s, i + 2)
        x.append(ALPHA[(b10 >> 18)])
        x.append(ALPHA[((b10 >> 12) & 63)])
        x.append(ALPHA[((b10 >> 6) & 63)])
        x.append(ALPHA[(b10 & 63)])
    i=imax
    print(i, len(s))
    if len(s) - imax ==1:
        b10 = getbyte(s, i) << 16
        x.append(ALPHA[(b10 >> 18)] + ALPHA[((b10 >> 12) & 63)] + PAD_CHAR + PAD_CHAR)
    if len(s) - imax == 2:
        b10 = (getbyte(s, i) << 16) | (getbyte(s, i + 1) << 8)
        x.append(ALPHA[(b10 >> 18)] + ALPHA[((b10 >> 12) & 63)] +
                 ALPHA[((b10 >> 6) & 63)] + PAD_CHAR)

    return "".join(x)

if __name__ == '__main__':
    print(get_base64("132456"))
