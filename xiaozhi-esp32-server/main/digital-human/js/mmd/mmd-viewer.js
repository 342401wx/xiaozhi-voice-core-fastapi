import * as THREE from 'three';
import { MMDLoader } from 'three/addons/loaders/MMDLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

class MMDViewer {
    constructor(container) {
        this.container = container;
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.controls = null;
        this.model = null;
        this.bones = {};
        this.morphTargets = {};
        this.commonBones = null;
        this.animationId = null;
        this.idleMixer = null;
        this.idleAction = null;
        this.idleMotionClip = null;
        this.idleMotionUrl = null;
        this.idleMotionReady = false;
        this.idleMotionActive = false;
        this.idleMotionFinishedHandler = null;
        this.idleAudio = null;
        this.idleAudioUrl = null;
        this.idleAudioReady = false;
        this.idleAudioBlocked = false;
        this.idleAudioError = null;
        this.idleAudioEndedHandler = null;
        this.idleDelayMs = 12000;
        this.lastActivityAt = performance.now();
        this.clock = new THREE.Clock();
        this.isTalking = false;
        this.mouse = { x: 0, y: 0 };
        this.bodyMotion = { x: 0, y: 0, velocityX: 0, velocityY: 0 };
        this.lastPointer = { x: 0, y: 0, time: 0 };
        this.poseApplied = false;
        this.poseTransitionActive = false;
        this.poseTransitionStart = 0;
        this.poseTransitionDurationMs = 850;
        this.poseTransitionCurrentDurationMs = 850;
        this.poseTransitionSource = null;
        this.poseTransitionTarget = null;
        this.resizeHandler = () => this.resize();
        this.pointerHandler = (event) => this.updatePointer(event);
        this.activityHandler = () => this.markUserActivity();
        this.parentActivityTargets = [];
    }

    async init(modelUrl, options = {}) {
        if (!this.container) {
            throw new Error('MMD 容器不存在');
        }

        if (Number.isFinite(options.idleDelayMs)) {
            this.idleDelayMs = Math.max(3000, options.idleDelayMs);
        }
        if (options.idleAudioUrl) {
            this.setupIdleAudio(options.idleAudioUrl);
        }

        if (!this.renderer) {
            this.setupScene();
        }

        if (!this.model) {
            await this.loadModel(modelUrl);
        }

        if (options.idleMotionUrl) {
            await this.loadIdleMotion(options.idleMotionUrl);
        }

        this.show();
        this.start();
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = null;

        this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
        this.camera.position.set(0, 12, 34);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.58;
        this.renderer.setClearColor(0x000000, 0);
        this.container.appendChild(this.renderer.domElement);

        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.target.set(0, 10, 0);
        this.controls.minDistance = 18;
        this.controls.maxDistance = 48;
        this.controls.enablePan = false;
        this.controls.enableRotate = false;
        this.controls.enableZoom = false;

        const ambientLight = new THREE.HemisphereLight(0xfff3e8, 0x514b57, 1.4);
        const keyLight = new THREE.DirectionalLight(0xffe0bd, 3.28);
        keyLight.position.set(3.5, 8, 7);
        const fillLight = new THREE.DirectionalLight(0xdce3ff, 1.42);
        fillLight.position.set(-6, 4, 5);
        const faceLight = new THREE.DirectionalLight(0xffedd8, 3.22);
        faceLight.position.set(0, 5, 10);
        const rimLight = new THREE.DirectionalLight(0xffb783, 1.02);
        rimLight.position.set(0, 6, -8);
        this.scene.add(ambientLight, keyLight, fillLight, faceLight, rimLight);

        this.attachActivityListeners();
        this.resize();
    }

    attachActivityListeners() {
        window.addEventListener('resize', this.resizeHandler);
        window.addEventListener('pointermove', this.pointerHandler);
        window.addEventListener('pointerdown', this.activityHandler);
        window.addEventListener('keydown', this.activityHandler);
        window.addEventListener('wheel', this.activityHandler);
        window.addEventListener('touchstart', this.activityHandler);

        try {
            if (window.parent && window.parent !== window && window.parent.document) {
                const parentDoc = window.parent.document;
                ['pointermove', 'pointerdown', 'keydown', 'wheel', 'touchstart'].forEach((type) => {
                    parentDoc.addEventListener(type, this.activityHandler);
                    this.parentActivityTargets.push({ target: parentDoc, type });
                });
            }
        } catch (error) {
            console.debug('父页面活动监听不可用:', error);
        }
    }

    detachActivityListeners() {
        window.removeEventListener('resize', this.resizeHandler);
        window.removeEventListener('pointermove', this.pointerHandler);
        window.removeEventListener('pointerdown', this.activityHandler);
        window.removeEventListener('keydown', this.activityHandler);
        window.removeEventListener('wheel', this.activityHandler);
        window.removeEventListener('touchstart', this.activityHandler);

        this.parentActivityTargets.forEach(({ target, type }) => {
            target.removeEventListener(type, this.activityHandler);
        });
        this.parentActivityTargets = [];
    }

    loadModel(modelUrl) {
        return new Promise((resolve, reject) => {
            const loader = new MMDLoader();
            loader.load(
                modelUrl,
                (mesh) => {
                    this.model = mesh;
                    this.model.position.set(0, -8, 0);
                    this.model.rotation.y = 0;
                    this.model.scale.setScalar(1.0);
                    this.prepareModel();
                    this.scene.add(this.model);
                    this.fitCamera();
                    resolve(mesh);
                },
                undefined,
                reject
            );
        });
    }

    setupIdleAudio(audioUrl) {
        if (!audioUrl || this.idleAudioUrl === audioUrl) return;

        this.idleAudioUrl = audioUrl;
        this.idleAudioReady = false;
        this.idleAudioBlocked = false;
        this.idleAudioError = null;
        this.idleAudioEndedHandler = null;
        this.idleAudio = new Audio(audioUrl);
        this.idleAudio.preload = 'auto';
        this.idleAudio.loop = false;
        this.idleAudio.volume = 0.95;
        this.idleAudioEndedHandler = () => this.updateDebugInfo();
        this.idleAudio.addEventListener('canplaythrough', () => {
            this.idleAudioReady = true;
            this.updateDebugInfo();
        }, { once: true });
        this.idleAudio.addEventListener('error', () => {
            this.idleAudioReady = false;
            this.idleAudioError = this.idleAudio?.error?.message || 'audio load error';
            this.updateDebugInfo();
        });
        this.idleAudio.addEventListener('ended', this.idleAudioEndedHandler);
        this.idleAudio.load();
        this.updateDebugInfo();
    }

    loadIdleMotion(motionUrl) {
        if (!motionUrl || !this.model) return Promise.resolve(null);
        if (this.idleMotionReady && this.idleMotionUrl === motionUrl) return Promise.resolve(this.idleMotionClip);

        this.idleMotionUrl = motionUrl;
        this.idleMotionReady = false;
        this.idleMotionActive = false;
        if (this.idleMixer && this.idleMotionFinishedHandler) {
            this.idleMixer.removeEventListener('finished', this.idleMotionFinishedHandler);
        }
        this.idleMotionFinishedHandler = null;

        return new Promise((resolve) => {
            const loader = new MMDLoader();
            loader.loadAnimation(
                motionUrl,
                this.model,
                (clip) => {
                    this.idleMixer = new THREE.AnimationMixer(this.model);
                    this.idleMotionClip = clip;
                    this.idleAction = this.idleMixer.clipAction(clip);
                    this.idleAction.enabled = true;
                    this.idleAction.setLoop(THREE.LoopOnce, 1);
                    this.idleAction.clampWhenFinished = true;
                    this.idleAction.stop();
                    this.idleMotionFinishedHandler = (event) => {
                        if (event.action === this.idleAction) {
                            this.finishIdleMotion();
                        }
                    };
                    this.idleMixer.addEventListener('finished', this.idleMotionFinishedHandler);
                    this.idleMotionReady = true;
                    this.lastActivityAt = performance.now();
                    this.updateDebugInfo();
                    resolve(clip);
                },
                undefined,
                (error) => {
                    console.warn('胡桃待机动作加载失败:', error);
                    this.idleMotionReady = false;
                    this.updateDebugInfo();
                    resolve(null);
                }
            );
        });
    }

    fitCamera() {
        if (!this.model) return;

        const box = new THREE.Box3().setFromObject(this.model);
        const size = new THREE.Vector3();
        const center = new THREE.Vector3();
        box.getSize(size);
        box.getCenter(center);

        const height = Math.max(size.y, 1);
        const distance = height * 1.62;
        this.controls.target.set(center.x, center.y + height * 0.12, center.z);
        this.camera.position.set(center.x, center.y + height * 0.24, center.z + distance);
        this.camera.lookAt(this.controls.target);
        this.camera.updateProjectionMatrix();
        this.controls.update();
    }

    prepareModel() {
        this.bones = {};
        this.morphTargets = {};
        this.commonBones = null;
        this.poseApplied = false;

        this.model.traverse((child) => {
            if (child.isBone) {
                this.bones[child.name] = child;
            }

            if (child.isSkinnedMesh || child.isMesh) {
                this.tuneMaterials(child);
                if (child.morphTargetDictionary && child.morphTargetInfluences) {
                    Object.keys(child.morphTargetDictionary).forEach((name) => {
                        this.morphTargets[name] = {
                            mesh: child,
                            index: child.morphTargetDictionary[name]
                        };
                    });
                }
            }
        });

        this.cacheCommonBones();
        this.applyRestPose();
        this.updateDebugInfo();
    }

    tuneMaterials(mesh) {
        const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        materials.forEach((material) => {
            if (!material) return;

            const materialName = `${material.name || ''} ${material.map?.name || ''} ${material.map?.image?.src || ''}`;
            const isSkin = /面|face|skin/i.test(materialName);
            const isHair = /发|髪|hair/i.test(materialName);
            const isCloth = /服|cloth|body|衣/i.test(materialName);

            material.toneMapped = true;
            material.needsUpdate = true;

            if (material.map) {
                material.map.colorSpace = THREE.SRGBColorSpace;
                if (material.map.image) {
                    material.map.needsUpdate = true;
                }
            }

            if (material.color) {
                if (isSkin) {
                    material.color.setRGB(1.16, 1.07, 0.99);
                } else if (isHair) {
                    material.color.setRGB(0.99, 0.76, 0.68);
                } else if (isCloth) {
                    material.color.setRGB(1.0, 0.92, 0.84);
                } else {
                    material.color.multiplyScalar(1.07);
                }
            }

            if (material.emissive) {
                if (isSkin) {
                    material.emissive.setRGB(0.046, 0.034, 0.025);
                } else if (isHair) {
                    material.emissive.setRGB(0.027, 0.015, 0.011);
                } else if (isCloth) {
                    material.emissive.setRGB(0.034, 0.024, 0.017);
                } else {
                    material.emissive.setRGB(0.017, 0.014, 0.012);
                }
            }

            if ('shininess' in material) {
                material.shininess = Math.min(material.shininess || 0, 8);
            }
        });
    }

    cacheCommonBones() {
        this.commonBones = {
            head: this.findBone(['頭', 'head']),
            neck: this.findBone(['首', 'neck']),
            upperBody: this.findBone(['上半身', 'upperbody', 'upper_body']),
            leftShoulder: this.findBone(['左肩', 'shoulder_l', 'leftshoulder']),
            rightShoulder: this.findBone(['右肩', 'shoulder_r', 'rightshoulder']),
            leftArm: this.findBone(['左腕', 'arm_l', 'leftarm']),
            rightArm: this.findBone(['右腕', 'arm_r', 'rightarm']),
            leftElbow: this.findBone(['左ひじ', '左肘', 'elbow_l', 'leftelbow']),
            rightElbow: this.findBone(['右ひじ', '右肘', 'elbow_r', 'rightelbow']),
            leftWrist: this.findBone(['左手首', 'wrist_l', 'lefthand']),
            rightWrist: this.findBone(['右手首', 'wrist_r', 'righthand']),
            leftEye: this.findBone(['左目', 'eye_l', 'lefteye']),
            rightEye: this.findBone(['右目', 'eye_r', 'righteye'])
        };
    }

    findBone(names) {
        const normalizedNames = names.map((name) => this.normalizeName(name));
        return Object.values(this.bones).find((bone) => {
            const normalized = this.normalizeName(bone.name);
            return normalizedNames.some((name) => normalized.includes(name));
        }) || null;
    }

    normalizeName(name) {
        return String(name || '')
            .toLowerCase()
            .replace(/[\s_\-.]/g, '');
    }

    applyRestPose() {
        if (!this.commonBones || this.poseApplied) return;

        this.setBoneRotation(this.commonBones.leftShoulder, THREE.MathUtils.degToRad(-2), THREE.MathUtils.degToRad(-6), THREE.MathUtils.degToRad(-6));
        this.setBoneRotation(this.commonBones.rightShoulder, THREE.MathUtils.degToRad(-2), THREE.MathUtils.degToRad(6), THREE.MathUtils.degToRad(6));
        this.setBoneRotation(this.commonBones.leftArm, THREE.MathUtils.degToRad(0), THREE.MathUtils.degToRad(8), THREE.MathUtils.degToRad(-28));
        this.setBoneRotation(this.commonBones.rightArm, THREE.MathUtils.degToRad(0), THREE.MathUtils.degToRad(-8), THREE.MathUtils.degToRad(28));
        this.setBoneRotation(this.commonBones.leftElbow, THREE.MathUtils.degToRad(0), THREE.MathUtils.degToRad(6), THREE.MathUtils.degToRad(-4));
        this.setBoneRotation(this.commonBones.rightElbow, THREE.MathUtils.degToRad(0), THREE.MathUtils.degToRad(-6), THREE.MathUtils.degToRad(4));
        this.setBoneRotation(this.commonBones.leftWrist, THREE.MathUtils.degToRad(2), THREE.MathUtils.degToRad(8), THREE.MathUtils.degToRad(-5));
        this.setBoneRotation(this.commonBones.rightWrist, THREE.MathUtils.degToRad(2), THREE.MathUtils.degToRad(-8), THREE.MathUtils.degToRad(5));
        this.poseApplied = true;
    }

    updateDebugInfo() {
        window.__hutaoDebug = {
            boneNames: Object.keys(this.bones),
            commonBones: Object.fromEntries(
                Object.entries(this.commonBones || {}).map(([key, bone]) => [key, bone ? bone.name : null])
            ),
            morphNames: Object.keys(this.morphTargets),
            materialNames: [],
            idleMotion: {
                url: this.idleMotionUrl,
                ready: this.idleMotionReady,
                active: this.idleMotionActive,
                delayMs: this.idleDelayMs,
                duration: this.idleMotionClip?.duration || null,
                idleForMs: Math.max(0, performance.now() - this.lastActivityAt)
            },
            idleAudio: {
                url: this.idleAudioUrl,
                ready: this.idleAudioReady,
                blocked: this.idleAudioBlocked,
                error: this.idleAudioError,
                paused: this.idleAudio?.paused ?? true,
                currentTime: this.idleAudio?.currentTime || 0,
                duration: Number.isFinite(this.idleAudio?.duration) ? this.idleAudio.duration : null
            },
            transition: {
                active: this.poseTransitionActive,
                durationMs: this.poseTransitionCurrentDurationMs,
                progress: this.poseTransitionActive
                    ? THREE.MathUtils.clamp((performance.now() - this.poseTransitionStart) / Math.max(this.poseTransitionCurrentDurationMs, 1), 0, 1)
                    : 0
            }
        };

        if (!this.model) return;

        this.model.traverse((child) => {
            if (!child.material) return;
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            materials.forEach((material) => {
                window.__hutaoDebug.materialNames.push({
                    name: material.name || '',
                    color: material.color ? `#${material.color.getHexString()}` : null,
                    map: material.map?.image?.src || material.map?.name || null
                });
            });
        });
    }

    markUserActivity() {
        this.lastActivityAt = performance.now();
        if (this.idleMotionActive) {
            this.exitIdleMotion();
        }
    }

    startIdleAudio() {
        if (!this.idleAudio) return;

        this.idleAudioBlocked = false;
        this.idleAudioError = null;
        try {
            this.idleAudio.pause();
            this.idleAudio.currentTime = 0;
            const playPromise = this.idleAudio.play();
            if (playPromise && typeof playPromise.catch === 'function') {
                playPromise.catch((error) => {
                    this.idleAudioBlocked = true;
                    this.idleAudioError = error?.message || String(error);
                    this.updateDebugInfo();
                });
            }
        } catch (error) {
            this.idleAudioBlocked = true;
            this.idleAudioError = error?.message || String(error);
        }
        this.updateDebugInfo();
    }

    stopIdleAudio() {
        if (!this.idleAudio) return;

        this.idleAudio.pause();
        try {
            this.idleAudio.currentTime = 0;
        } catch (error) {
            this.idleAudioError = error?.message || String(error);
        }
        this.updateDebugInfo();
    }

    setBoneRotation(bone, x = 0, y = 0, z = 0) {
        if (!bone) return;
        bone.rotation.set(x, y, z);
        bone.updateMatrixWorld(true);
    }

    capturePoseState() {
        if (!this.model) return null;

        const state = {
            model: {
                position: this.model.position.clone(),
                quaternion: this.model.quaternion.clone(),
                scale: this.model.scale.clone()
            },
            bones: [],
            morphs: []
        };

        this.model.traverse((child) => {
            if (child.isBone) {
                state.bones.push({
                    object: child,
                    position: child.position.clone(),
                    quaternion: child.quaternion.clone(),
                    scale: child.scale.clone()
                });
            }

            if ((child.isSkinnedMesh || child.isMesh) && child.morphTargetInfluences) {
                state.morphs.push({
                    object: child,
                    values: Array.from(child.morphTargetInfluences)
                });
            }
        });

        return state;
    }

    applyPoseState(state) {
        if (!this.model || !state) return;

        if (state.model) {
            this.model.position.copy(state.model.position);
            this.model.quaternion.copy(state.model.quaternion);
            this.model.scale.copy(state.model.scale);
        }

        state.bones.forEach((boneState) => {
            const bone = boneState.object;
            if (!bone) return;
            bone.position.copy(boneState.position);
            bone.quaternion.copy(boneState.quaternion);
            bone.scale.copy(boneState.scale);
        });

        state.morphs.forEach((morphState) => {
            const influences = morphState.object?.morphTargetInfluences;
            if (!influences) return;
            const count = Math.min(influences.length, morphState.values.length);
            for (let i = 0; i < count; i += 1) {
                influences[i] = morphState.values[i];
            }
        });

        this.model.updateMatrixWorld(true);
    }

    interpolatePoseState(source, target, amount) {
        if (!this.model || !source || !target) return;

        const t = THREE.MathUtils.clamp(amount, 0, 1);
        if (source.model && target.model) {
            this.model.position.lerpVectors(source.model.position, target.model.position, t);
            this.model.quaternion.slerpQuaternions(source.model.quaternion, target.model.quaternion, t);
            this.model.scale.lerpVectors(source.model.scale, target.model.scale, t);
        }

        const boneCount = Math.min(source.bones.length, target.bones.length);
        for (let i = 0; i < boneCount; i += 1) {
            const sourceBone = source.bones[i];
            const targetBone = target.bones[i];
            const bone = sourceBone.object;
            if (!bone || bone !== targetBone.object) continue;

            bone.position.lerpVectors(sourceBone.position, targetBone.position, t);
            bone.quaternion.slerpQuaternions(sourceBone.quaternion, targetBone.quaternion, t);
            bone.scale.lerpVectors(sourceBone.scale, targetBone.scale, t);
        }

        const morphCount = Math.min(source.morphs.length, target.morphs.length);
        for (let i = 0; i < morphCount; i += 1) {
            const sourceMorph = source.morphs[i];
            const targetMorph = target.morphs[i];
            const influences = sourceMorph.object?.morphTargetInfluences;
            if (!influences || sourceMorph.object !== targetMorph.object) continue;

            const valueCount = Math.min(influences.length, sourceMorph.values.length, targetMorph.values.length);
            for (let j = 0; j < valueCount; j += 1) {
                influences[j] = THREE.MathUtils.lerp(sourceMorph.values[j], targetMorph.values[j], t);
            }
        }

        this.model.updateMatrixWorld(true);
    }

    cancelPoseTransition() {
        this.poseTransitionActive = false;
        this.poseTransitionSource = null;
        this.poseTransitionTarget = null;
    }

    startRestPoseTransition(durationMs = this.poseTransitionDurationMs, sourceState = null) {
        if (!this.model) return false;

        const source = sourceState || this.capturePoseState();
        this.model.pose();
        this.poseApplied = false;
        this.applyRestPose();
        const target = this.capturePoseState();
        this.applyPoseState(source);

        this.poseApplied = false;
        this.poseTransitionSource = source;
        this.poseTransitionTarget = target;
        this.poseTransitionStart = performance.now();
        this.poseTransitionCurrentDurationMs = Math.max(120, durationMs);
        this.poseTransitionActive = true;
        this.updateDebugInfo();
        return true;
    }

    updatePoseTransition() {
        if (!this.poseTransitionActive) return false;

        const progress = THREE.MathUtils.clamp(
            (performance.now() - this.poseTransitionStart) / Math.max(this.poseTransitionCurrentDurationMs, 1),
            0,
            1
        );
        const eased = progress * progress * (3 - 2 * progress);
        this.interpolatePoseState(this.poseTransitionSource, this.poseTransitionTarget, eased);

        if (progress >= 1) {
            this.applyPoseState(this.poseTransitionTarget);
            this.poseApplied = true;
            this.cancelPoseTransition();
            this.updateDebugInfo();
        }

        return true;
    }

    updatePointer(event) {
        this.markUserActivity();

        const rect = this.container?.getBoundingClientRect();
        if (!rect || rect.width === 0 || rect.height === 0) return;

        const nextX = THREE.MathUtils.clamp(((event.clientX - rect.left) / rect.width - 0.5) * 2, -1, 1);
        const nextY = THREE.MathUtils.clamp(((event.clientY - rect.top) / rect.height - 0.5) * -2, -1, 1);
        const now = performance.now();

        if (this.lastPointer.time) {
            const deltaTime = Math.max((now - this.lastPointer.time) / 1000, 0.016);
            this.bodyMotion.velocityX = THREE.MathUtils.clamp((nextX - this.lastPointer.x) / deltaTime, -8, 8);
            this.bodyMotion.velocityY = THREE.MathUtils.clamp((nextY - this.lastPointer.y) / deltaTime, -8, 8);
        }

        this.mouse.x = nextX;
        this.mouse.y = nextY;
        this.lastPointer = { x: nextX, y: nextY, time: now };
    }

    enterIdleMotion() {
        if (!this.idleMotionReady || !this.idleAction || this.idleMotionActive || this.poseTransitionActive || this.isTalking) return;

        this.cancelPoseTransition();
        this.idleMotionActive = true;
        this.poseApplied = false;
        if (this.model) {
            this.model.pose();
        }
        this.idleMixer.stopAllAction();
        this.idleAction.reset();
        this.idleAction.enabled = true;
        this.idleAction.setEffectiveWeight(1);
        this.idleAction.timeScale = 1;
        this.idleAction.paused = false;
        this.idleAction.play();
        this.startIdleAudio();
        this.updateDebugInfo();
    }

    finishIdleMotion() {
        if (!this.idleMotionActive) return;

        const source = this.model ? this.capturePoseState() : null;
        const shouldTransition = Boolean(source);
        this.idleMotionActive = false;
        this.stopIdleAudio();
        if (this.idleAction) {
            this.idleAction.stop();
        }
        if (shouldTransition) {
            this.startRestPoseTransition(this.poseTransitionDurationMs, source);
        }
        if (this.model && !shouldTransition) {
            this.model.pose();
            this.poseApplied = false;
            this.applyRestPose();
        }
        this.lastActivityAt = performance.now();
        this.updateDebugInfo();
    }

    exitIdleMotion(smooth = true) {
        if (!this.idleMotionActive) return;

        const source = smooth && this.model ? this.capturePoseState() : null;
        const shouldTransition = Boolean(source);
        this.idleMotionActive = false;
        if (this.idleAction) {
            this.idleAction.stop();
        }
        this.stopIdleAudio();
        if (shouldTransition) {
            this.startRestPoseTransition(560, source);
        }
        if (this.model && !shouldTransition) {
            this.model.pose();
            this.poseApplied = false;
            this.applyRestPose();
        }
        this.updateDebugInfo();
    }

    updateIdleMotion(delta) {
        if (!this.idleMotionReady || !this.idleMixer || !this.idleAction) return;

        const now = performance.now();
        if (this.isTalking) {
            this.markUserActivity();
            return;
        }

        if (!this.idleMotionActive && now - this.lastActivityAt >= this.idleDelayMs) {
            this.enterIdleMotion();
        }

        if (this.idleMotionActive) {
            this.idleMixer.update(delta);
        }
    }

    applyLookAt(elapsed) {
        if (!this.commonBones) return;

        const lookX = THREE.MathUtils.clamp(this.mouse.x, -1, 1);
        const lookY = THREE.MathUtils.clamp(this.mouse.y, -1, 1);
        const headYaw = lookX * 0.18;
        const headPitch = -lookY * 0.11 + Math.sin(elapsed * 0.85) * 0.018;
        const neckYaw = lookX * 0.07;
        const eyeYaw = lookX * 0.16;
        const eyePitch = -lookY * 0.08;

        if (this.commonBones.head) {
            this.commonBones.head.rotation.y = headYaw;
            this.commonBones.head.rotation.x = headPitch;
        }
        if (this.commonBones.neck) {
            this.commonBones.neck.rotation.y = neckYaw;
            this.commonBones.neck.rotation.x = headPitch * 0.35;
        }
        if (this.commonBones.leftEye) {
            this.commonBones.leftEye.rotation.y = eyeYaw;
            this.commonBones.leftEye.rotation.x = eyePitch;
        }
        if (this.commonBones.rightEye) {
            this.commonBones.rightEye.rotation.y = eyeYaw;
            this.commonBones.rightEye.rotation.x = eyePitch;
        }
    }

    applyIdleMotion(elapsed) {
        if (!this.commonBones) return;

        const breath = Math.sin(elapsed * 1.35);
        if (this.commonBones.upperBody) {
            this.commonBones.upperBody.rotation.x = breath * 0.012;
            this.commonBones.upperBody.rotation.z = Math.sin(elapsed * 0.55) * 0.008;
        }

        if (this.commonBones.head) {
            this.commonBones.head.rotation.z = this.isTalking
                ? Math.sin(elapsed * 7) * 0.018
                : Math.sin(elapsed * 0.7) * 0.006;
        }

        this.applyBlink(elapsed);
    }

    applyBodyMotion(elapsed) {
        if (!this.commonBones) return;

        this.bodyMotion.x += (this.mouse.x - this.bodyMotion.x) * 0.08;
        this.bodyMotion.y += (this.mouse.y - this.bodyMotion.y) * 0.08;
        this.bodyMotion.velocityX *= 0.88;
        this.bodyMotion.velocityY *= 0.88;

        const swayX = this.bodyMotion.x;
        const swayY = this.bodyMotion.y;
        const kickX = THREE.MathUtils.clamp(this.bodyMotion.velocityX, -5, 5);
        const kickY = THREE.MathUtils.clamp(this.bodyMotion.velocityY, -5, 5);
        const handSwing = Math.sin(elapsed * 2.2) * 0.01;

        if (this.commonBones.upperBody) {
            this.commonBones.upperBody.rotation.x += -swayY * 0.055 + kickY * 0.006;
            this.commonBones.upperBody.rotation.y = swayX * 0.11 + kickX * 0.012;
            this.commonBones.upperBody.rotation.z += -swayX * 0.045;
        }

        this.setBoneRotation(
            this.commonBones.leftShoulder,
            THREE.MathUtils.degToRad(-2) + swayY * 0.012,
            THREE.MathUtils.degToRad(-6) + swayX * 0.02,
            THREE.MathUtils.degToRad(-6) - swayX * 0.028 + kickX * 0.004
        );
        this.setBoneRotation(
            this.commonBones.rightShoulder,
            THREE.MathUtils.degToRad(-2) + swayY * 0.012,
            THREE.MathUtils.degToRad(6) + swayX * 0.02,
            THREE.MathUtils.degToRad(6) - swayX * 0.028 + kickX * 0.004
        );
        this.setBoneRotation(
            this.commonBones.leftArm,
            kickY * 0.004,
            THREE.MathUtils.degToRad(8) + swayX * 0.014,
            THREE.MathUtils.degToRad(-28) - swayX * 0.035 + kickX * 0.007 + handSwing
        );
        this.setBoneRotation(
            this.commonBones.rightArm,
            kickY * 0.004,
            THREE.MathUtils.degToRad(-8) + swayX * 0.014,
            THREE.MathUtils.degToRad(28) - swayX * 0.035 + kickX * 0.007 - handSwing
        );
        this.setBoneRotation(
            this.commonBones.leftElbow,
            0,
            THREE.MathUtils.degToRad(6) + swayX * 0.01,
            THREE.MathUtils.degToRad(-4) - kickX * 0.004
        );
        this.setBoneRotation(
            this.commonBones.rightElbow,
            0,
            THREE.MathUtils.degToRad(-6) + swayX * 0.01,
            THREE.MathUtils.degToRad(4) - kickX * 0.004
        );
    }

    applyBlink(elapsed) {
        const blink = this.morphTargets['まばたき'] || this.morphTargets['blink'] || this.morphTargets['Blink'];
        if (!blink) return;

        const cycle = elapsed % 4.8;
        const amount = cycle > 4.45 ? Math.sin((cycle - 4.45) / 0.35 * Math.PI) : 0;
        blink.mesh.morphTargetInfluences[blink.index] = THREE.MathUtils.clamp(amount, 0, 1);
    }

    show() {
        if (this.container) {
            this.container.classList.add('active');
        }
    }

    hide() {
        if (this.container) {
            this.container.classList.remove('active');
        }
        this.exitIdleMotion(false);
        this.cancelPoseTransition();
        this.stop();
        this.stopTalking();
    }

    start() {
        if (this.animationId) return;
        this.clock.start();
        const tick = () => {
            this.animationId = requestAnimationFrame(tick);
            const delta = this.clock.getDelta();
            const elapsed = this.clock.getElapsedTime();

            if (this.model) {
                this.updateIdleMotion(delta);

                if (this.idleMotionActive) {
                    this.model.rotation.y = 0;
                    this.model.position.y = -8;
                } else if (this.poseTransitionActive) {
                    this.updatePoseTransition();
                } else {
                    this.model.rotation.y = Math.sin(elapsed * 0.45) * 0.012;
                    this.model.position.y = -8 + Math.sin(elapsed * 1.2) * 0.035;
                    this.applyRestPose();
                    this.applyLookAt(elapsed);
                    this.applyIdleMotion(elapsed);
                    this.applyBodyMotion(elapsed);
                }
            }

            if (this.controls) {
                this.controls.update();
            }

            if (this.renderer && this.scene && this.camera) {
                this.renderer.render(this.scene, this.camera);
            }
        };
        tick();
    }

    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    startTalking() {
        this.isTalking = true;
        this.markUserActivity();
    }

    stopTalking() {
        this.isTalking = false;
    }

    resize() {
        if (!this.container || !this.renderer || !this.camera) return;

        const width = this.container.clientWidth || window.innerWidth;
        const height = this.container.clientHeight || window.innerHeight;
        this.renderer.setSize(width, height, false);
        this.camera.aspect = width / Math.max(height, 1);
        this.camera.updateProjectionMatrix();
    }

    destroy() {
        this.hide();
        this.detachActivityListeners();

        if (this.model) {
            this.scene.remove(this.model);
            this.model.traverse((child) => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) {
                    const materials = Array.isArray(child.material) ? child.material : [child.material];
                    materials.forEach((material) => material.dispose());
                }
            });
            this.model = null;
        }

        if (this.renderer) {
            this.renderer.dispose();
            this.renderer.domElement.remove();
            this.renderer = null;
        }

        this.scene = null;
        this.camera = null;
        this.controls = null;
        if (this.idleMixer && this.idleMotionFinishedHandler) {
            this.idleMixer.removeEventListener('finished', this.idleMotionFinishedHandler);
        }
        this.idleMixer = null;
        this.idleAction = null;
        this.idleMotionClip = null;
        this.idleMotionFinishedHandler = null;
        if (this.idleAudio && this.idleAudioEndedHandler) {
            this.idleAudio.removeEventListener('ended', this.idleAudioEndedHandler);
        }
        this.stopIdleAudio();
        this.cancelPoseTransition();
        this.idleAudioEndedHandler = null;
        this.idleAudio = null;
        this.bones = {};
        this.morphTargets = {};
        this.commonBones = null;
    }
}

export { MMDViewer };
