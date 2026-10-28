import * as THREE from './vendor/three.module.js'
import { GLTFLoader } from './vendor/GLTFLoader.js'
import { RoomEnvironment } from './vendor/RoomEnvironment.js'
/** One canvas per mounted companion. Caller owns lifetime and observed motion. */
export async function mount(canvas, onReady, onError) {
  let dead = false,
    frame = 0,
    last = 0,
    mixer,
    model,
    eyes = [],
    active,
    motion = 'idle',
    ready = false,
    turning = false,
    turnTime = 0,
    sighTime = 0
  const reduced = matchMedia('(prefers-reduced-motion: reduce)')
  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: 'low-power',
  })
  // Reserve pixels for the 1.35x brand entrance as well as the resting pose.
  renderer.setPixelRatio(Math.min(devicePixelRatio * 1.35, 3))
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 0.96
  const scene = new THREE.Scene(),
    camera = new THREE.OrthographicCamera(-2, 2, 2.325, -2.325, 0.1, 100)
  // Rotate the actual model in 3D; never flip the 2D canvas into a flat line.
  const pivot = new THREE.Group()
  scene.add(pivot)
  camera.position.set(0, 2.05, 9)
  camera.lookAt(0, 1.7, 0)
  const pmrem = new THREE.PMREMGenerator(renderer),
    room = new RoomEnvironment(),
    env = pmrem.fromScene(room, 0.04)
  scene.environment = env.texture
  room.dispose()
  pmrem.dispose()
  scene.add(new THREE.HemisphereLight(0xfff3df, 0xbb8c6a, 1.5))
  const key = new THREE.DirectionalLight(0xfff1dd, 2.4)
  key.position.set(-3, 5, 5)
  scene.add(key)
  const fill = new THREE.DirectionalLight(0xffb378, 1)
  fill.position.set(4, 3, -2)
  scene.add(fill)
  const clips = {}
  const stop = () => {
    cancelAnimationFrame(frame)
    frame = 0
    last = 0
  }
  function draw() {
    if (ready && !dead) renderer.render(scene, camera)
  }
  function tick(t) {
    frame = 0
    if (dead || document.hidden || reduced.matches || !ready) return
    const dt = Math.min((t - (last || t)) / 1000, 0.05)
    last = t
    mixer.update(dt)
    if (motion === 'sigh') {
      sighTime = Math.min(sighTime + dt, 1.6)
      const progress = sighTime / 1.6
      const nod = Math.sin(Math.PI * progress) ** 2
      const breath = Math.sin(Math.PI * progress) * 0.025
      pivot.rotation.x = nod * 0.16
      pivot.position.y = -nod * 0.1
      pivot.scale.set(1 + breath, 1 - breath, 1 + breath)
      for (const eye of eyes) {
        const blink = eye.morphTargetDictionary?.Blink100
        if (blink !== undefined)
          eye.morphTargetInfluences[blink] = Math.max(eye.morphTargetInfluences[blink], nod * 0.8)
      }
      canvas.dataset.sighProgress = String(progress)
      if (progress === 1) play('idle')
    }
    if (turning) {
      turnTime = Math.min(turnTime + dt, 0.48)
      const progress = turnTime / 0.48
      pivot.rotation.y = Math.PI * 2 * (progress * progress * (3 - 2 * progress))
      if (progress === 1) {
        turning = false
        pivot.rotation.y = 0
        canvas.dataset.turning = 'false'
      }
    }
    draw()
    frame = requestAnimationFrame(tick)
  }
  function resume() {
    if (!frame && !dead && !document.hidden && !reduced.matches && ready)
      frame = requestAnimationFrame(tick)
    else draw()
  }
  function resize() {
    const w = canvas.parentElement.clientWidth,
      h = canvas.parentElement.clientHeight
    if (!w || !h) return
    renderer.setSize(w, h, false)
    camera.left = (-4.65 * w) / h / 2
    camera.right = -camera.left
    camera.updateProjectionMatrix()
    draw()
  }
  function play(name) {
    const changed = motion !== name
    motion = name
    if (!ready) return
    if (name !== 'sigh') {
      pivot.rotation.x = 0
      pivot.position.y = 0
      pivot.scale.set(1, 1, 1)
    } else if (changed) {
      sighTime = 0
      canvas.dataset.sighCount = String(Number(canvas.dataset.sighCount || 0) + 1)
    }
    const clipName =
      name === 'sigh'
        ? 'cautious'
        : ['thinking', 'working'].includes(name)
          ? 'thinking_notes'
          : name
    const next = clips[clipName]
    if (!next) return
    const offset = name === 'thinking' ? 3.7 : name === 'working' ? 0.8 : 0
    canvas.dataset.motion = name
    canvas.dataset.clip = clipName
    if (next === active) {
      if (changed) {
        next.time = offset
        mixer.update(0)
        draw()
      }
      return
    }
    const old = active
    active = next
    next.reset().setEffectiveWeight(1).play()
    next.time = offset
    if (old) old.crossFadeTo(next, 0.25, false)
    if (reduced.matches) {
      mixer.stopAllAction()
      next.play()
      next.time = offset || Math.min(next.getClip().duration * 0.3, 1)
      mixer.update(0)
      draw()
    }
    resume()
  }
  function visibility() {
    stop()
    resume()
  }
  function preference() {
    stop()
    if (reduced.matches) {
      turning = false
      pivot.rotation.y = 0
      canvas.dataset.turning = 'false'
    }
    active = null
    play(motion)
  }
  function lost(e) {
    e.preventDefault()
    dispose()
    onError()
  }
  const observer = new ResizeObserver(resize)
  observer.observe(canvas)
  document.addEventListener('visibilitychange', visibility)
  reduced.addEventListener('change', preference)
  canvas.addEventListener('webglcontextlost', lost)
  function dispose() {
    if (dead) return
    dead = true
    stop()
    observer.disconnect()
    document.removeEventListener('visibilitychange', visibility)
    reduced.removeEventListener('change', preference)
    canvas.removeEventListener('webglcontextlost', lost)
    mixer?.stopAllAction()
    model?.traverse((o) => {
      if (o.isMesh) {
        o.geometry.dispose()
        for (const m of [].concat(o.material)) m.dispose()
      }
    })
    env.dispose()
    renderer.dispose()
  }
  new GLTFLoader().load(
    new URL('./huohuo-animated.glb', import.meta.url).href,
    (gltf) => {
      if (dead) {
        gltf.scene.traverse((o) => {
          if (o.isMesh) {
            o.geometry.dispose()
            ;[].concat(o.material).forEach((m) => m.dispose())
          }
        })
        return
      }
      model = gltf.scene
      eyes = ['EyeLeft', 'EyeRight'].map((name) => model.getObjectByName(name)).filter(Boolean)
      pivot.add(model)
      model.traverse((o) => {
        if (!o.isMesh) return
        o.frustumCulled = false
        if (o.name === 'SpiritBody' || o.name.startsWith('Hand')) {
          o.material.dispose()
          o.material = new THREE.MeshPhysicalMaterial({
            color: 0xff992f,
            roughness: 0.4,
            metalness: 0,
            clearcoat: 0.22,
            clearcoatRoughness: 0.3,
            envMapIntensity: 0.45,
          })
          if (o.name === 'SpiritBody') {
            o.material.name = 'HuohuoWarmCheeks-r2'
            o.material.onBeforeCompile = (shader) => {
              shader.vertexShader = shader.vertexShader
                .replace(
                  '#include <common>',
                  '#include <common>\n varying vec3 vHuohuoLocalPosition;',
                )
                .replace(
                  '#include <begin_vertex>',
                  '#include <begin_vertex>\n vHuohuoLocalPosition = position;',
                )
              shader.fragmentShader = shader.fragmentShader.replace(
                '#include <common>',
                '#include <common>\n varying vec3 vHuohuoLocalPosition;',
              )
              shader.fragmentShader = shader.fragmentShader.replace(
                '#include <color_fragment>',
                `#include <color_fragment>
                float facing = pow(abs(dot(normalize(vNormal), normalize(vViewPosition))), 1.8);
                diffuseColor.rgb = mix(vec3(0.95, 0.18, 0.018), vec3(1.0, 0.39, 0.055), facing);
                // GLTF 使用 Y-up：对应 Blender 的 X / Z 与朝前的 -Y。
                vec2 cheekPosition = vec2(
                  (abs(vHuohuoLocalPosition.x) - 0.58) / 0.215,
                  (vHuohuoLocalPosition.y - 1.56) / 0.105
                );
                float cheek = (1.0 - smoothstep(0.25, 1.0, dot(cheekPosition, cheekPosition)))
                  * smoothstep(0.55, 0.8, vHuohuoLocalPosition.z) * 0.88;
                diffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.0, 0.112, 0.15), cheek);`,
              )
              // Align display chroma with the approved icon after tone mapping.
              // Retain highlight value, restore chroma, then reduce the small yellow cast.
              shader.fragmentShader = shader.fragmentShader.replace(
                '#include <colorspace_fragment>',
                `#include <colorspace_fragment>
                float huohuoPeak = max(gl_FragColor.r, max(gl_FragColor.g, gl_FragColor.b));
                gl_FragColor.rgb = clamp(vec3(huohuoPeak) + (gl_FragColor.rgb - vec3(huohuoPeak)) * 1.6, 0.0, 1.0);
                float huohuoChroma = huohuoPeak - min(gl_FragColor.r, min(gl_FragColor.g, gl_FragColor.b));
                if (gl_FragColor.r >= gl_FragColor.g && gl_FragColor.g >= gl_FragColor.b) {
                  gl_FragColor.g = max(gl_FragColor.b, gl_FragColor.g - huohuoChroma * 0.04);
                }`,
              )
            }
            o.material.customProgramCacheKey = () => 'huohuo-warm-cheeks-r3-color'
          }
        } else if (o.name.startsWith('Eye')) {
          o.material.color.set(0x25120b)
          o.material.roughness = 0.16
        }
      })
      mixer = new THREE.AnimationMixer(model)
      gltf.animations.forEach((c) => (clips[c.name] = mixer.clipAction(c)))
      ready = true
      resize()
      play(motion)
      onReady(canvas.parentElement.clientHeight >= 280 ? canvas.toDataURL('image/png') : undefined)
    },
    undefined,
    () => {
      if (!dead) onError()
    },
  )
  function turn() {
    if (!ready || dead || reduced.matches || document.hidden) return
    turning = true
    turnTime = 0
    canvas.dataset.turning = 'true'
    canvas.dataset.turnCount = String(Number(canvas.dataset.turnCount || 0) + 1)
    resume()
  }
  return { play, turn, dispose }
}
