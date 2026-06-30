let authenticated = $state(false)

export const session = {
  get authenticated() {
    return authenticated
  },
  open() {
    authenticated = true
  },
}
