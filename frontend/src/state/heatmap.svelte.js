import { sensors, minutes } from '../data/temperature.js'

let readings = $state(sensors.map(() => minutes.map(() => 0)))

export const heatmap = {
  get readings() {
    return readings
  },
  set(next) {
    readings = next
  },
}
