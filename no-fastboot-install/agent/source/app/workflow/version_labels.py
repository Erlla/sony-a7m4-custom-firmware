from product_integrity import pinned, state_path

def consistent(bcd, api):
    if type(bcd) is not int or type(api) is not int or (not 0 < bcd <= 39321) or (not 0 <= api <= 4294967295):
        return False
    digits = [bcd >> shift & 15 for shift in (12, 8, 4, 0)]
    if any((digit > 9 for digit in digits)):
        return False
    major, minor = (digits[0] * 10 + digits[1], digits[2] * 10 + digits[3])
    return api == major << 16 | minor
