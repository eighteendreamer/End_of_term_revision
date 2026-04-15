/**
 * 加密工具函数
 */

/**
 * MD5加密函数
 * @param {string} string - 需要加密的字符串
 * @returns {string} - MD5加密后的字符串
 */
export function md5(string) {
  function rotateLeft(value, shift) {
    return (value << shift) | (value >>> (32 - shift))
  }

  function addUnsigned(x, y) {
    const lsw = (x & 0xffff) + (y & 0xffff)
    const msw = (x >> 16) + (y >> 16) + (lsw >> 16)
    return (msw << 16) | (lsw & 0xffff)
  }

  function md5F(x, y, z) {
    return (x & y) | (~x & z)
  }

  function md5G(x, y, z) {
    return (x & z) | (y & ~z)
  }

  function md5H(x, y, z) {
    return x ^ y ^ z
  }

  function md5I(x, y, z) {
    return y ^ (x | ~z)
  }

  function md5FF(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(md5F(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }

  function md5GG(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(md5G(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }

  function md5HH(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(md5H(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }

  function md5II(a, b, c, d, x, s, ac) {
    a = addUnsigned(a, addUnsigned(addUnsigned(md5I(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }

  function convertToWordArray(string) {
    let lWordCount
    const lMessageLength = string.length
    const lNumberOfWordsTemp1 = lMessageLength + 8
    const lNumberOfWordsTemp2 = (lNumberOfWordsTemp1 - (lNumberOfWordsTemp1 % 64)) / 64
    const lNumberOfWords = (lNumberOfWordsTemp2 + 1) * 16
    const lWordArray = new Array(lNumberOfWords - 1)
    let lBytePosition = 0
    let lByteCount = 0

    while (lByteCount < lMessageLength) {
      lWordCount = (lByteCount - (lByteCount % 4)) / 4
      lBytePosition = (lByteCount % 4) * 8
      lWordArray[lWordCount] = lWordArray[lWordCount] | (string.charCodeAt(lByteCount) << lBytePosition)
      lByteCount++
    }

    lWordCount = (lByteCount - (lByteCount % 4)) / 4
    lBytePosition = (lByteCount % 4) * 8
    lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition)
    lWordArray[lNumberOfWords - 2] = lMessageLength << 3
    lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29

    return lWordArray
  }

  function wordToHex(lValue) {
    let wordToHexValue = ''
    let wordToHexValueTemp = ''
    let lByte, lCount

    for (lCount = 0; lCount <= 3; lCount++) {
      lByte = (lValue >>> (lCount * 8)) & 255
      wordToHexValueTemp = '0' + lByte.toString(16)
      wordToHexValue = wordToHexValue + wordToHexValueTemp.substr(wordToHexValueTemp.length - 2, 2)
    }

    return wordToHexValue
  }

  function utf8Encode(string) {
    string = string.replace(/\r\n/g, '\n')
    let utftext = ''

    for (let n = 0; n < string.length; n++) {
      const c = string.charCodeAt(n)

      if (c < 128) {
        utftext += String.fromCharCode(c)
      } else if (c > 127 && c < 2048) {
        utftext += String.fromCharCode((c >> 6) | 192)
        utftext += String.fromCharCode((c & 63) | 128)
      } else {
        utftext += String.fromCharCode((c >> 12) | 224)
        utftext += String.fromCharCode(((c >> 6) & 63) | 128)
        utftext += String.fromCharCode((c & 63) | 128)
      }
    }

    return utftext
  }

  let x = []
  let k, AA, BB, CC, DD, a, b, c, d
  const S11 = 7, S12 = 12, S13 = 17, S14 = 22
  const S21 = 5, S22 = 9, S23 = 14, S24 = 20
  const S31 = 4, S32 = 11, S33 = 16, S34 = 23
  const S41 = 6, S42 = 10, S43 = 15, S44 = 21

  string = utf8Encode(string)
  x = convertToWordArray(string)

  a = 0x67452301
  b = 0xefcdab89
  c = 0x98badcfe
  d = 0x10325476

  for (k = 0; k < x.length; k += 16) {
    AA = a
    BB = b
    CC = c
    DD = d
    a = md5FF(a, b, c, d, x[k + 0], S11, 0xd76aa478)
    d = md5FF(d, a, b, c, x[k + 1], S12, 0xe8c7b756)
    c = md5FF(c, d, a, b, x[k + 2], S13, 0x242070db)
    b = md5FF(b, c, d, a, x[k + 3], S14, 0xc1bdceee)
    a = md5FF(a, b, c, d, x[k + 4], S11, 0xf57c0faf)
    d = md5FF(d, a, b, c, x[k + 5], S12, 0x4787c62a)
    c = md5FF(c, d, a, b, x[k + 6], S13, 0xa8304613)
    b = md5FF(b, c, d, a, x[k + 7], S14, 0xfd469501)
    a = md5FF(a, b, c, d, x[k + 8], S11, 0x698098d8)
    d = md5FF(d, a, b, c, x[k + 9], S12, 0x8b44f7af)
    c = md5FF(c, d, a, b, x[k + 10], S13, 0xffff5bb1)
    b = md5FF(b, c, d, a, x[k + 11], S14, 0x895cd7be)
    a = md5FF(a, b, c, d, x[k + 12], S11, 0x6b901122)
    d = md5FF(d, a, b, c, x[k + 13], S12, 0xfd987193)
    c = md5FF(c, d, a, b, x[k + 14], S13, 0xa679438e)
    b = md5FF(b, c, d, a, x[k + 15], S14, 0x49b40821)
    a = md5GG(a, b, c, d, x[k + 1], S21, 0xf61e2562)
    d = md5GG(d, a, b, c, x[k + 6], S22, 0xc040b340)
    c = md5GG(c, d, a, b, x[k + 11], S23, 0x265e5a51)
    b = md5GG(b, c, d, a, x[k + 0], S24, 0xe9b6c7aa)
    a = md5GG(a, b, c, d, x[k + 5], S21, 0xd62f105d)
    d = md5GG(d, a, b, c, x[k + 10], S22, 0x2441453)
    c = md5GG(c, d, a, b, x[k + 15], S23, 0xd8a1e681)
    b = md5GG(b, c, d, a, x[k + 4], S24, 0xe7d3fbc8)
    a = md5GG(a, b, c, d, x[k + 9], S21, 0x21e1cde6)
    d = md5GG(d, a, b, c, x[k + 14], S22, 0xc33707d6)
    c = md5GG(c, d, a, b, x[k + 3], S23, 0xf4d50d87)
    b = md5GG(b, c, d, a, x[k + 8], S24, 0x455a14ed)
    a = md5GG(a, b, c, d, x[k + 13], S21, 0xa9e3e905)
    d = md5GG(d, a, b, c, x[k + 2], S22, 0xfcefa3f8)
    c = md5GG(c, d, a, b, x[k + 7], S23, 0x676f02d9)
    b = md5GG(b, c, d, a, x[k + 12], S24, 0x8d2a4c8a)
    a = md5HH(a, b, c, d, x[k + 5], S31, 0xfffa3942)
    d = md5HH(d, a, b, c, x[k + 8], S32, 0x8771f681)
    c = md5HH(c, d, a, b, x[k + 11], S33, 0x6d9d6122)
    b = md5HH(b, c, d, a, x[k + 14], S34, 0xfde5380c)
    a = md5HH(a, b, c, d, x[k + 1], S31, 0xa4beea44)
    d = md5HH(d, a, b, c, x[k + 4], S32, 0x4bdecfa9)
    c = md5HH(c, d, a, b, x[k + 7], S33, 0xf6bb4b60)
    b = md5HH(b, c, d, a, x[k + 10], S34, 0xbebfbc70)
    a = md5HH(a, b, c, d, x[k + 13], S31, 0x289b7ec6)
    d = md5HH(d, a, b, c, x[k + 0], S32, 0xeaa127fa)
    c = md5HH(c, d, a, b, x[k + 3], S33, 0xd4ef3085)
    b = md5HH(b, c, d, a, x[k + 6], S34, 0x4881d05)
    a = md5HH(a, b, c, d, x[k + 9], S31, 0xd9d4d039)
    d = md5HH(d, a, b, c, x[k + 12], S32, 0xe6db99e5)
    c = md5HH(c, d, a, b, x[k + 15], S33, 0x1fa27cf8)
    b = md5HH(b, c, d, a, x[k + 2], S34, 0xc4ac5665)
    a = md5II(a, b, c, d, x[k + 0], S41, 0xf4292244)
    d = md5II(d, a, b, c, x[k + 7], S42, 0x432aff97)
    c = md5II(c, d, a, b, x[k + 14], S43, 0xab9423a7)
    b = md5II(b, c, d, a, x[k + 5], S44, 0xfc93a039)
    a = md5II(a, b, c, d, x[k + 12], S41, 0x655b59c3)
    d = md5II(d, a, b, c, x[k + 3], S42, 0x8f0ccc92)
    c = md5II(c, d, a, b, x[k + 10], S43, 0xffeff47d)
    b = md5II(b, c, d, a, x[k + 1], S44, 0x85845dd1)
    a = md5II(a, b, c, d, x[k + 8], S41, 0x6fa87e4f)
    d = md5II(d, a, b, c, x[k + 15], S42, 0xfe2ce6e0)
    c = md5II(c, d, a, b, x[k + 6], S43, 0xa3014314)
    b = md5II(b, c, d, a, x[k + 13], S44, 0x4e0811a1)
    a = md5II(a, b, c, d, x[k + 4], S41, 0xf7537e82)
    d = md5II(d, a, b, c, x[k + 11], S42, 0xbd3af235)
    c = md5II(c, d, a, b, x[k + 2], S43, 0x2ad7d2bb)
    b = md5II(b, c, d, a, x[k + 9], S44, 0xeb86d391)
    a = addUnsigned(a, AA)
    b = addUnsigned(b, BB)
    c = addUnsigned(c, CC)
    d = addUnsigned(d, DD)
  }

  return (wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)).toLowerCase()
}
