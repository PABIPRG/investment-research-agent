import test from 'node:test'
import assert from 'node:assert/strict'
const THREE = await import(new URL('../../product/ui/assets/companion/vendor/three.module.js', import.meta.url).href)
import { configureAction } from '../product/ui/assets/companion/knock-motion.js'
import { createInteraction } from '../product/ui/assets/companion/interaction-motion.js'

test('敲窗只播放一次，保留接触姿势；下一条动作恢复循环', () => {
  const model = new THREE.Object3D() as any, mixer = new THREE.AnimationMixer(model)
  const clip = new THREE.AnimationClip('gentle_knock', 1, [
    new THREE.NumberKeyframeTrack('.position[x]', [0, .5, 1], [0, 1, 0]),
  ])
  const action = mixer.clipAction(clip)!, canvas = {dataset: {} as Record<string,string>}
  let finished = 0
  mixer.addEventListener('finished', () => finished++)
  configureAction(action, 'gentle_knock', canvas, THREE.LoopOnce, THREE.LoopRepeat).reset().play()
  mixer.update(.5); assert.equal(model.position.x, 1)
  mixer.update(.6); mixer.update(5)
  assert.equal(finished, 1); assert.equal(action.paused, true)
  assert.equal(canvas.dataset.knockCount, '1')
  configureAction(action, 'awaiting_reply', canvas, THREE.LoopOnce, THREE.LoopRepeat).reset().play()
  assert.equal(action.loop, THREE.LoopRepeat); assert.equal(action.clampWhenFinished, false)
  mixer.update(2.5); assert.equal(action.paused, false)
  assert.equal(canvas.dataset.knockCount, '1')
})

test('原转身动作仍然有界，复位不留下旋转', () => {
  const pivot = {rotation: {y: 0}}, canvas = {dataset: {} as Record<string,string>}
  const motion = createInteraction(pivot, canvas)
  motion.turn(); for (let i = 0; i < 12; i++) motion.tick(.05)
  assert.equal(pivot.rotation.y, 0); assert.equal(canvas.dataset.turnCount, '1')
  motion.turn(); motion.tick(.1); motion.reset()
  assert.equal(pivot.rotation.y, 0); assert.equal(canvas.dataset.turning, 'false')
})
