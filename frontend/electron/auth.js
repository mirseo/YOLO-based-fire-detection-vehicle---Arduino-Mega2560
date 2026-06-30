const crypto = require('crypto')

function hash(value) {
  return crypto.createHash('sha256').update(String(value), 'utf8').digest()
}

function safeEqual(a, b) {
  return crypto.timingSafeEqual(hash(a), hash(b))
}

function verifyPassword(rawPassword) {
  const password = String(rawPassword)
  if (password.length === 0) {
    return { ok: false, message: '비밀번호를 입력해 주세요' }
  }

  const expected = process.env.AUTH_PASSWORD || ''
  if (!expected) {
    return { ok: false, message: '인증 서비스를 사용할 수 없어요' }
  }

  if (!safeEqual(password, expected)) {
    return { ok: false, message: '비밀번호가 일치하지 않아요' }
  }

  return { ok: true }
}

module.exports = { verifyPassword }
