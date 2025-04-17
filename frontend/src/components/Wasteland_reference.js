import React, { useEffect, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import * as CANNON from 'cannon';
import '../styles/western-theme.css';
import hitSound1 from '../sounds/hit1.mp3';
import hitSound2 from '../sounds/hit2.mp3';
import hitSound3 from '../sounds/hit3.mp3';
import hitSound4 from '../sounds/hit4.mp3';
import hitSound5 from '../sounds/hit5.mp3';
import hitSound6 from '../sounds/hit6.mp3';
import hitSound7 from '../sounds/hit7.mp3';
import hitSound8 from '../sounds/hit8.mp3';
import hitSound9 from '../sounds/hit9.mp3';
import hitSound10 from '../sounds/hit10.mp3';
import hitSound11 from '../sounds/hit11.mp3';
import hitSound12 from '../sounds/hit12.mp3';
import skullIcon from '../images/skull.png'; // Import the skull icon image
import ParticleSystem from './ParticleSystem'; // Import the ParticleSystem component

const hitSounds = [
  hitSound1, hitSound2, hitSound3, hitSound4, hitSound5, hitSound6,
  hitSound7, hitSound8, hitSound9, hitSound10, hitSound11, hitSound12
];

// Add an array to store the blood splatter animation frames
const bloodSplatterFrames = Array.from({ length: 30 }, (_, i) => 
  `https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/main/frontend/media/frame${i + 1}.png`
);

const Wasteland = ({ volume }) => {
  const mountRef = useRef(null);
  const cameraRef = useRef(null);
  const [remainingBandits, setRemainingBandits] = useState(1); // Changed from 5
  const banditsRef = useRef([]);
  const banditBodiesRef = useRef([]);
  const hitboxesRef = useRef([]);
  const skullIconsRef = useRef([]);
  const hitBanditsRef = useRef(new Set());
  const history = useHistory();
  const particleSystemRef = useRef(null);
  const sceneRef = useRef(new THREE.Scene()); // Define the scene variable

  useEffect(() => {
    const scene = sceneRef.current; // Use the scene variable
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    cameraRef.current = camera;
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true; // Enable shadow maps
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mountRef.current.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; // Enable damping (inertia)
    controls.dampingFactor = 0.25; // Damping factor
    controls.screenSpacePanning = false; // Disable panning
    controls.enableZoom = true; // Enable zooming
    controls.enablePan = true; // Enable panning

    const world = new CANNON.World();
    world.gravity.set(0, -25, 0); // Set gravity
    
    // Set smaller step size and more iterations for better stability
    world.solver.iterations = 20; // Increased from default 10
    world.solver.tolerance = 0.001; // More precise

    // Define collision groups for consistent detection
    const COLLISION_GROUP_GROUND = 1;
    const COLLISION_GROUP_BODY = 2;
    const COLLISION_GROUP_LIMBS = 4;

    // Create materials for better physics
    const groundMaterial = new CANNON.Material("groundMaterial");
    const ragdollMaterial = new CANNON.Material("ragdollMaterial");
    
    // Create ground plane with proper collision settings
    const groundBody = new CANNON.Body({
      mass: 0, // Mass of 0 makes the body static
      material: groundMaterial,
      collisionFilterGroup: COLLISION_GROUP_GROUND,
      collisionFilterMask: COLLISION_GROUP_BODY | COLLISION_GROUP_LIMBS
    });
    
    // Add a plane shape
    const groundShape = new CANNON.Plane();
    groundBody.addShape(groundShape);
    
    // Also add a box shape for better collision detection
    const groundBoxShape = new CANNON.Box(new CANNON.Vec3(50, 1.0, 50)); // Thicker box
    groundBody.addShape(groundBoxShape, new CANNON.Vec3(0, -1.0, 0)); // Position it just below the plane
    
    groundBody.quaternion.setFromEuler(-Math.PI / 2, 0, 0);
    
    // Add ground position to ensure it's at y=0
    groundBody.position.set(0, 0, 0);
    world.addBody(groundBody);
    
    // Create contact material with better friction and restitution
    const ground_ragdoll_cm = new CANNON.ContactMaterial(
      groundMaterial, 
      ragdollMaterial, 
      {
        friction: 0.8,        // Higher friction to prevent sliding
        restitution: 0.2,     // Less bounce to prevent instability
        contactEquationStiffness: 1e8,
        contactEquationRelaxation: 3,
        frictionEquationStiffness: 1e8  // Add friction stiffness
      }
    );
    
    world.addContactMaterial(ground_ragdoll_cm);

    // Load floor texture
    const textureLoader = new THREE.TextureLoader();
    const floorTexture = textureLoader.load('https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/main/frontend/media/soil3.png');
    floorTexture.wrapS = THREE.RepeatWrapping;
    floorTexture.wrapT = THREE.RepeatWrapping;
    floorTexture.repeat.set(1, 1); // Single texture

    // Create a larger transparent mesh
    const extendedFloorGeometry = new THREE.PlaneGeometry(100, 100, 32, 32);
    const extendedFloorMaterial = new THREE.ShaderMaterial({
      uniforms: {
        center: { value: new THREE.Vector2(0, 0) },
        radius: { value: 50.0 },
        floorTexture: { value: floorTexture }
      },
      vertexShader: `
        varying vec2 vUv;
        varying float vDistance;

        void main() {
          vUv = uv; // Simple UV mapping without scaling
          vec4 worldPosition = modelMatrix * vec4(position, 1.0);
          vDistance = length(worldPosition.xz);
          gl_Position = projectionMatrix * viewMatrix * worldPosition;
        }
      `,
      fragmentShader: `
        uniform float radius;
        uniform sampler2D floorTexture;
        varying vec2 vUv;
        varying float vDistance;

        void main() {
          vec4 color = texture2D(floorTexture, vUv);
          float alpha = 1.0 - smoothstep(radius * 0.5, radius, vDistance);
          gl_FragColor = vec4(color.rgb, color.a * alpha);
        }
      `,
      transparent: true,
      side: THREE.DoubleSide
    });
    const extendedFloorMesh = new THREE.Mesh(extendedFloorGeometry, extendedFloorMaterial);
    extendedFloorMesh.rotation.x = -Math.PI / 2;
    extendedFloorMesh.receiveShadow = true; // Enable shadows for the extended floor
    scene.add(extendedFloorMesh);

    // Load skybox
    const skyboxTexture = textureLoader.load('https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/main/frontend/media/skybox_desert1.png', () => {
      const rt = new THREE.WebGLCubeRenderTarget(skyboxTexture.image.height);
      rt.fromEquirectangularTexture(renderer, skyboxTexture);
      scene.background = rt.texture;
    });

    const loader = new GLTFLoader();

    // Load bandit model
    loader.load('https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/main/frontend/media/50backup.glb', (gltf) => {
      for (let i = 0; i < 1; i++) { // Single bandit
        const bandit = gltf.scene.clone();

        // Initialize ragdoll physics for the bandit's skeleton
        const bonePhysicsMap = createRagdollForSkinnedMesh(bandit, world, scene);
        bandit.userData.bonePhysicsMap = bonePhysicsMap;
        if(bonePhysicsMap.size === 0) {
          console.warn('No skinned mesh found in the model!');
        }

        // Use the first bone as the main physics body for positioning the bandit
        const skinnedMesh = bandit.getObjectByProperty('type', 'SkinnedMesh');
        if (skinnedMesh && skinnedMesh.skeleton && skinnedMesh.skeleton.bones.length > 0) {
          const rootBone = skinnedMesh.skeleton.bones[0];
          if (bonePhysicsMap.has(rootBone.name)) {
            banditBodiesRef.current.push(bonePhysicsMap.get(rootBone.name).body);
          }
        }

        // Position the bandit higher above the ground initially
        bandit.position.set(Math.random() * 10 - 5, 3, Math.random() * 10 - 5);
        
        // Apply the position to all physics bodies and FREEZE IMMEDIATELY
        if (bandit.userData.bonePhysicsMap) {
          bandit.userData.bonePhysicsMap.forEach((obj) => {
            obj.body.position.y += 3; // Lift all bones 3 units up
            
            // FREEZE PHYSICS IMMEDIATELY to prevent any initial falling
            obj.body.initialMass = obj.body.mass; 
            obj.body.mass = 0; // Make it static
            obj.body.updateMassProperties();
            obj.body.velocity.set(0, 0, 0);
            obj.body.angularVelocity.set(0, 0, 0);
            obj.body.frozen = true;
            
            // Force position update for the physics body
            obj.body.updateMassProperties();
            obj.body.updateBoundingRadius();
            
            // Make debug meshes more visible
            obj.debugMesh.material.opacity = 0.7;
            obj.debugMesh.material.transparent = true;
            
            // Update debug mesh position
            obj.debugMesh.position.copy(obj.body.position);
          });
        }
        
        bandit.traverse((node) => {
          if (node.isMesh) {
            node.castShadow = true;
            node.receiveShadow = true;
            node.material.shadowSide = THREE.FrontSide;
          }
        });
        scene.add(bandit);
        banditsRef.current.push(bandit);
        
        // Now set the pose while bodies are already frozen
        setDefaultPose(bandit);
        
        // After setting the pose, align the physics bodies with the visual bones
        setTimeout(() => {
          bandit.updateMatrixWorld(true);
          
          if (bandit.userData.bonePhysicsMap) {
            // First pass: get and store all bone positions and rotations
            const boneWorldPositions = new Map();
            bandit.userData.bonePhysicsMap.forEach((obj) => {
              const boneWorldPos = new THREE.Vector3();
              obj.bone.getWorldPosition(boneWorldPos);
              
              const boneWorldQuat = new THREE.Quaternion();
              obj.bone.getWorldQuaternion(boneWorldQuat);
              
              boneWorldPositions.set(obj.bone.name, {
                position: boneWorldPos.clone(),
                quaternion: boneWorldQuat.clone()
              });
            });
            
            // Second pass: apply positions and rotations to physics bodies
            bandit.userData.bonePhysicsMap.forEach((obj) => {
              const boneData = boneWorldPositions.get(obj.bone.name);
              if (boneData) {
                const boneWorldPos = boneData.position;
                const boneWorldQuat = boneData.quaternion;
                
                // Apply a vertical offset if needed to fix alignment
                const verticalOffset = -0.5; // Adjust this value to fix misalignment
                boneWorldPos.y += verticalOffset;
                
                // Update physics body position and rotation (will remain frozen)
                obj.body.position.copy(boneWorldPos);
                obj.body.quaternion.copy(boneWorldQuat);
                
                // Store the initial quaternion for locked rotation
                obj.body.originalQuaternion = new CANNON.Quaternion().copy(boneWorldQuat);
                obj.body.originalPosition = new CANNON.Vec3().copy(boneWorldPos);
                
                // Update debug mesh
                obj.debugMesh.position.copy(boneWorldPos);
                obj.debugMesh.quaternion.copy(boneWorldQuat);
                
                // Update hit mesh if it exists
                if (obj.hitMesh) {
                  obj.hitMesh.position.copy(boneWorldPos);
                  obj.hitMesh.quaternion.copy(boneWorldQuat);
                }
                
                // Store reference position for later use
                obj.referencePosition = boneWorldPos.clone();
                obj.referenceQuaternion = boneWorldQuat.clone();
              }
            });
          }
        }, 100); // Short delay to ensure pose is applied
      }
    });

    // Add sunlight
    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(10, 10, 10);
    light.castShadow = true; // Enable shadows for the light
    light.shadow.mapSize.width = 1024;
    light.shadow.mapSize.height = 1024;
    light.shadow.camera.near = 0.5;
    light.shadow.camera.far = 500;
    light.shadow.camera.left = -50;
    light.shadow.camera.right = 50;
    light.shadow.camera.top = 50;
    light.shadow.camera.bottom = -50;
    scene.add(light);

    // Add helpers for debugging
    const lightHelper = new THREE.DirectionalLightHelper(light);
    scene.add(lightHelper);

    const shadowCameraHelper = new THREE.CameraHelper(light.shadow.camera);
    scene.add(shadowCameraHelper);

    camera.position.z = 5;

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onMouseClick = (event) => {
      sceneRef.current.updateMatrixWorld(true);
      const mouse = new THREE.Vector2();
      mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
      
      const raycaster = new THREE.Raycaster();
      raycaster.near = 0.1;
      raycaster.far = 1000;
      // Set a larger threshold to make hitting easier
      raycaster.params.Line.threshold = 0.2;
      raycaster.params.Points.threshold = 0.2;
      raycaster.setFromCamera(mouse, cameraRef.current);

      // Create an array of meshes to test for intersections
      const physicsMeshes = [];
      banditsRef.current.forEach((bandit, banditIndex) => {
        const bonePhysicsMap = bandit.userData.bonePhysicsMap;
        if (bonePhysicsMap) {
          bonePhysicsMap.forEach(physicsObj => {
            // Skip neutral_bone - hide and disable it
            if (physicsObj.bone.name === 'neutral_bone') return;
            
            if (physicsObj.debugMesh) {
              physicsMeshes.push(physicsObj.debugMesh);
              physicsObj.debugMesh.userData.banditIndex = banditIndex;
            }
            
            // Add the larger hit mesh for better collision detection
            if (physicsObj.hitMesh) {
              physicsMeshes.push(physicsObj.hitMesh);
              physicsObj.hitMesh.userData.banditIndex = banditIndex;
            }
          });
        }
      });
      
      // Check for intersections with any part of the model
      const intersects = raycaster.intersectObjects(physicsMeshes);
      if (intersects.length > 0) {
        const intersect = intersects[0];
        console.log("Hit object:", intersect.object.name, intersect.object.userData);
        
        // Find the bone or debug mesh that was hit
        let hitBone = null;
        let hitObject = intersect.object;
        let hitBandit = null;
        let hitBoneName = null;
        
        if (hitObject.userData.bonePhysics) {
          hitBone = hitObject.userData.bonePhysics;
          hitBoneName = hitBone.bone.name;
          hitBandit = hitBone.bandit;
        }

        // If we didn't find a specific bone, use the raycaster to find the bandit that was clicked
        if (!hitBandit && hitObject.userData.banditIndex !== undefined) {
          hitBandit = banditsRef.current[hitObject.userData.banditIndex];
        }
        
        if (hitBandit) {
          const bonePhysicsMap = hitBandit.userData.bonePhysicsMap;
          
          // If we didn't find a specific bone, choose a random visible bone from this bandit
          if (!hitBone) {
            // Get all non-neutral bones
            const availableBones = Array.from(bonePhysicsMap.values()).filter(
              obj => obj.bone.name !== 'neutral_bone'
            );
            
            if (availableBones.length > 0) {
              // Choose a random bone to apply the hit to
              const randomIndex = Math.floor(Math.random() * availableBones.length);
              hitBone = availableBones[randomIndex];
            }
          }
          
          // Mark bandit as hit if not already hit
          if (!hitBanditsRef.current.has(hitBandit)) {
            hitBanditsRef.current.add(hitBandit);
            // Set remainingBandits to 0 so the Leave area button appears
            setRemainingBandits(0);
          }
          
          // Unfreeze the entire ragdoll when any part is hit
          unfreezeRagdoll(bonePhysicsMap);
          
          // Disable pose control once shot
          hitBandit.userData.poseEnabled = false;
          
          // Get intersection point in world space
          const intersectionPoint = intersect.point;
  
          // Only proceed if we have a hitBone to apply force to
          if (hitBone) {
            // Get the ray direction directly from the raycaster
            // This represents the direction of the shot from the camera
            const shotDirection = raycaster.ray.direction.clone().normalize();
            
            console.log("Shot direction from camera:", shotDirection);
            
            // This is the direction we want the impulse to be applied
            // It's the direction the bullet would travel
            const impulseMagnitude = 50; // Reduced from 150 for more stability
            
            // Create impulse vector directly from the shot direction
            const impulse = new CANNON.Vec3(
              shotDirection.x * impulseMagnitude,
              shotDirection.y * impulseMagnitude,
              shotDirection.z * impulseMagnitude
            );
            
            // Convert intersection point to local body space for impulse application
            const worldPoint = new CANNON.Vec3(
              intersectionPoint.x - hitBone.body.position.x,
              intersectionPoint.y - hitBone.body.position.y,
              intersectionPoint.z - hitBone.body.position.z
            );

            // Limit the world point to be inside the body's radius
            const maxRadius = 0.3;
            const wpLen = worldPoint.length();
            if (wpLen > maxRadius) {
              worldPoint.scale(maxRadius/wpLen, worldPoint);
            }
            
            // Apply impulse at the impact point in the direction of the shot
            hitBone.body.applyImpulse(impulse, worldPoint);
            console.log("Applied impulse in shot direction:", impulse);
            
            // Apply additional impulse to connected bones for more realistic effect
            if (hitBone.constraints) {
              hitBone.constraints.forEach(constraint => {
                // For each connected bone, apply a smaller impulse in the same direction
                const connectedBody = constraint.bodyA === hitBone.body ? constraint.bodyB : constraint.bodyA;
                if (connectedBody && connectedBody !== hitBone.body) {
                  // Apply a reduced impulse to connected parts
                  const spreadImpulse = new CANNON.Vec3(
                    shotDirection.x * impulseMagnitude * 0.3, // Reduced from 0.6
                    shotDirection.y * impulseMagnitude * 0.3,
                    shotDirection.z * impulseMagnitude * 0.3
                  );
                  connectedBody.applyImpulse(spreadImpulse, new CANNON.Vec3(0, 0, 0));
                }
              });
            }
            
            // Add a small upward component to the impulse to counter gravity
            setTimeout(() => {
              const upwardImpulse = new CANNON.Vec3(0, impulseMagnitude * 0.2, 0); // Reduced from 0.3
              hitBone.body.applyImpulse(upwardImpulse, new CANNON.Vec3(0, 0, 0));
              
              // Also reduce angular velocity for more stable movement
              hitBone.body.angularVelocity.scale(0.3, hitBone.body.angularVelocity); // Increased damping
            }, 20);
          }
          
          // Play a random hit sound
          const randomIndex = Math.floor(Math.random() * hitSounds.length);
          const audio = new Audio(hitSounds[randomIndex]);
          audio.volume = volume || 0.5;
          audio.play();
          
          // Add skull icon and camera shake effects
          const skullSprite = createSkullIcon(intersectionPoint);
          sceneRef.current.add(skullSprite);
          skullIconsRef.current.push({ sprite: skullSprite, banditIndex: 0 });
          
          // Add blood splatter sprite at hit location
          const bloodSprite = createBloodSplatterSprite(intersectionPoint);
          sceneRef.current.add(bloodSprite);
          
          applyCameraShake();
          
          // Create particle effect if available
          if (particleSystemRef.current && particleSystemRef.current.createImpactEffect) {
            particleSystemRef.current.createImpactEffect(intersectionPoint);
          }
        }
      }
    };
    
    // Add mouse over and out events
    const onMouseMove = (event) => {
      // Update the mouse position
      const mouse = new THREE.Vector2();
      mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
      
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(mouse, cameraRef.current);
      
      // Create array of physics meshes for hit testing
      const physicsMeshes = [];
      banditsRef.current.forEach(bandit => {
        const bonePhysicsMap = bandit.userData.bonePhysicsMap;
        if (bonePhysicsMap) {
          bonePhysicsMap.forEach(physicsObj => {
            if (physicsObj.debugMesh) {
              physicsMeshes.push(physicsObj.debugMesh);
            }
          });
        }
      });
      
      // Check for intersections
      const intersects = raycaster.intersectObjects(physicsMeshes);
      
      // Reset all debug meshes to normal
      physicsMeshes.forEach(mesh => {
        if (mesh.material) {
          mesh.material.color.set(0xff0000);
          mesh.material.opacity = 0.7;
        }
      });
      
      // Highlight only the intersected mesh
      if (intersects.length > 0) {
        const intersected = intersects[0].object;
        
        // Only change the color of the specific mesh that was hit
        intersected.material.color.set(0xffff00);
        intersected.material.opacity = 1.0;
        
        // Log which bone is being highlighted (for debugging)
        if (intersected.userData.bonePhysics && intersected.userData.bonePhysics.bone) {
          const boneName = intersected.userData.bonePhysics.bone.name;
          document.getElementById('debug') && (document.getElementById('debug').innerText = `Hovering over: ${boneName}`);
        }
        
        // Change cursor to pointer
        document.body.style.cursor = 'pointer';
      } else {
        // Reset cursor
        document.body.style.cursor = 'default';
      }
    };
    
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('pointerdown', onMouseClick);

    const createSkullIcon = (position) => {
      const spriteMap = new THREE.TextureLoader().load(skullIcon);
      const spriteMaterial = new THREE.SpriteMaterial({ 
        map: spriteMap,
        transparent: true,
        alphaTest: 0.5,
        depthTest: true,
        depthWrite: false,
        blending: THREE.NormalBlending
      });
      const sprite = new THREE.Sprite(spriteMaterial);
      sprite.position.set(position.x, position.y + 2, position.z);
      sprite.scale.set(0.5, 0.5, 0.5);
      return sprite;
    };

    const applyCameraShake = () => {
      const shakeIntensity = 0.1;
      const shakeDuration = 100; // in milliseconds

      const originalPosition = camera.position.clone();
      const shake = () => {
        camera.position.x = originalPosition.x + (Math.random() - 0.5) * shakeIntensity;
        camera.position.y = originalPosition.y + (Math.random() - 0.5) * shakeIntensity;
        camera.position.z = originalPosition.z + (Math.random() - 0.5) * shakeIntensity;
      };

      const resetCameraPosition = () => {
        camera.position.copy(originalPosition);
      };

      shake();
      setTimeout(resetCameraPosition, shakeDuration);
    };

    const debugSkeletonBones = (object) => {
      object.traverse((child) => {
          if (child.isSkinnedMesh) {
              console.log(`Skeleton bones for ${child.name}:`);
              child.skeleton.bones.forEach((bone) => {
                  console.log(`Bone: ${bone.name}, Position: ${bone.position}`);
              });
          }
      });
    };

    const createRagdollForSkinnedMesh = (model, world, scene) => {
      const bonePhysicsMap = new Map();
      // Create a base material template but don't use it directly
      const redMaterialTemplate = new THREE.MeshBasicMaterial({ 
        color: 0xff0000, 
        wireframe: true,
        transparent: true,
        opacity: 0.7
      });
      
      // Store arrays of bone groups for balancing
      const spineBones = [];
      const legBones = [];
      const footBones = [];
      
      // Traverse the model for skinned meshes
      model.traverse((child) => {
        if (child.isSkinnedMesh && child.skeleton) {
          child.skeleton.bones.forEach((bone) => {
            // Skip neutral_bone - hide and disable it
            if (bone.name === 'neutral_bone') {
              bone.visible = false;
              return;
            }
            
            const boneWorldPos = new THREE.Vector3();
            // Get world position of the bone - make sure the model matrices are updated first
            model.updateWorldMatrix(true, true);
            bone.getWorldPosition(boneWorldPos);
      
            // Estimate default bone size based on children distance if any are available.
            let boneSize = 0.1;
            if (bone.children.length > 0) {
              let maxDistance = 0;
              bone.children.forEach((childBone) => {
                const childPos = new THREE.Vector3();
                childBone.getWorldPosition(childPos);
                maxDistance = Math.max(maxDistance, boneWorldPos.distanceTo(childPos));
              });
              boneSize = maxDistance > 0 ? maxDistance : 0.1;
            }

            // Define custom settings for known bones with separate x, y, z multipliers.
            const boneSettings = {
              'Hips':           { mass: 5,  xMultiplier: 1.5, yMultiplier: 0.9, zMultiplier: 1.0 },  // Wider than tall
              'Spine':          { mass: 4,  xMultiplier: 1.2, yMultiplier: 1.4, zMultiplier: 0.9 },  // Taller than wide
              'Chest':          { mass: 7,  xMultiplier: 1.7, yMultiplier: 1.4, zMultiplier: 1.0 },  // Wider and taller
              
              // Legs - long rectangular shapes
              'RightUpperLeg':  { mass: 5,  xMultiplier: 0.8, yMultiplier: 1.6, zMultiplier: 0.8 },  // Tall rectangle
              'RightLowerLeg':  { mass: 4,  xMultiplier: 0.7, yMultiplier: 1.7, zMultiplier: 0.7 },  // Taller rectangle
              'RightFoot':      { mass: 2,  xMultiplier: 1.2, yMultiplier: 0.5, zMultiplier: 1.8 },  // Longer in z direction for forward
              'LeftUpperLeg':   { mass: 5,  xMultiplier: 0.8, yMultiplier: 1.6, zMultiplier: 0.8 },  // Tall rectangle
              'LeftLowerLeg':   { mass: 4,  xMultiplier: 0.7, yMultiplier: 1.7, zMultiplier: 0.7 },  // Taller rectangle
              'LeftFoot':       { mass: 2,  xMultiplier: 1.2, yMultiplier: 0.5, zMultiplier: 1.8 },  // Longer in z direction for forward
              
              // Arms - long thin shapes
              'RightUpperArm':  { mass: 2,  xMultiplier: 0.7, yMultiplier: 1.4, zMultiplier: 0.7 },  // Long thin cylinder
              'RightElbow':     { mass: 1.5,xMultiplier: 0.6, yMultiplier: 1.5, zMultiplier: 0.6 },  // Longer cylinder
              'RightHand':      { mass: 1,  xMultiplier: 1.0, yMultiplier: 0.7, zMultiplier: 1.3 },  // Larger hand
              'LeftUpperArm':   { mass: 2,  xMultiplier: 0.7, yMultiplier: 1.4, zMultiplier: 0.7 },  // Long thin cylinder
              'LeftElbow':      { mass: 1.5,xMultiplier: 0.6, yMultiplier: 1.5, zMultiplier: 0.6 },  // Longer cylinder
              'LeftHand':       { mass: 1,  xMultiplier: 1.0, yMultiplier: 0.7, zMultiplier: 1.3 },  // Larger hand
              
              // Head and neck
              'Neck':           { mass: 2,  xMultiplier: 0.7, yMultiplier: 0.9, zMultiplier: 0.7 },  // Cylindrical
              'Head':           { mass: 3,  xMultiplier: 1.8, yMultiplier: 1.8, zMultiplier: 1.8 },  // Much larger head
            };

            // Get the settings for the current bone, or use default values.
            const settings = boneSettings[bone.name] || { mass: Math.pow(boneSize, 3), xMultiplier: 1.2, yMultiplier: 1.2, zMultiplier: 1.2 };

            const boxWidth  = boneSize * settings.xMultiplier;
            const boxHeight = boneSize * settings.yMultiplier;
            const boxDepth  = boneSize * settings.zMultiplier;
            const halfExtents = new CANNON.Vec3(boxWidth / 2, boxHeight / 2, boxDepth / 2);
            const boxShape = new CANNON.Box(halfExtents);

            // Determine collision group and mask
            let collisionGroup = COLLISION_GROUP_BODY;
            let collisionFilter = COLLISION_GROUP_GROUND;
            
            if (bone.name.includes('Spine') || bone.name.includes('Hips') || 
                bone.name.includes('Chest') || bone.name.includes('Head')) {
              // Torso and head: don't collide with limbs
              collisionGroup = COLLISION_GROUP_BODY;
              collisionFilter = COLLISION_GROUP_GROUND;
              
              // Track spine bones for balancing
              if (bone.name.includes('Spine') || bone.name.includes('Hips') || bone.name.includes('Chest')) {
                spineBones.push(bone.name);
              }
            } else if (bone.name.includes('Leg') || bone.name.includes('Foot')) {
              // Legs: don't collide with other legs or arms
              collisionGroup = COLLISION_GROUP_LIMBS;
              collisionFilter = COLLISION_GROUP_GROUND | COLLISION_GROUP_BODY;
              
              // Track leg and foot bones for balancing
              if (bone.name.includes('Leg')) {
                legBones.push(bone.name);
              }
              if (bone.name.includes('Foot')) {
                footBones.push(bone.name);
              }
            } else if (bone.name.includes('Arm') || bone.name.includes('Hand')) {
              // Arms: don't collide with other arms or legs
              collisionGroup = COLLISION_GROUP_LIMBS;
              collisionFilter = COLLISION_GROUP_GROUND | COLLISION_GROUP_BODY;
            }

            // Create the physics body at the exact bone position
            const body = new CANNON.Body({
              mass: settings.mass,
              position: new CANNON.Vec3(boneWorldPos.x, boneWorldPos.y, boneWorldPos.z),
              shape: boxShape,
              material: ragdollMaterial,
              collisionFilterGroup: collisionGroup,
              collisionFilterMask: collisionFilter
            });
            
            // Store initial mass for unfreezing
            body.initialMass = settings.mass;
            body.frozen = false;
            
            // Add moderate damping for more natural movement while preventing excessive spinning
            body.angularDamping = 0.9;  // Reduced from 0.99 to allow some rotation
            body.linearDamping = 0.7;   // Reduced from 0.9 to allow more natural falling
            
            // Store initial quaternion for reference
            body.originalQuaternion = new CANNON.Quaternion().copy(body.quaternion);
            
            world.addBody(body);

            // Debug mesh should be positioned exactly at the bone position
            const boxGeometry = new THREE.BoxGeometry(boxWidth, boxHeight, boxDepth);
            const uniqueMaterial = redMaterialTemplate.clone();
            const debugMesh = new THREE.Mesh(boxGeometry, uniqueMaterial);
            debugMesh.name = `debug_${bone.name}`;
            // Set position exactly to match the bone world position
            debugMesh.position.copy(boneWorldPos);
            debugMesh.userData.bonePhysics = { 
              body: body, 
              bone: bone, 
              bandit: model 
            };
            
            // Create a larger invisible hitbox for better hit detection
            const hitGeometry = new THREE.BoxGeometry(
              boxWidth * 1.3, 
              boxHeight * 1.3, 
              boxDepth * 1.3
            );
            const hitMaterial = new THREE.MeshBasicMaterial({
              transparent: true,
              opacity: 0.0,
              visible: false
            });
            const hitMesh = new THREE.Mesh(hitGeometry, hitMaterial);
            hitMesh.name = `hit_${bone.name}`;
            hitMesh.position.copy(boneWorldPos);
            hitMesh.userData.bonePhysics = { 
              body: body, 
              bone: bone, 
              bandit: model 
            };
            scene.add(hitMesh);
            
            bonePhysicsMap.set(bone.name, { body, debugMesh, hitMesh, bone });
            scene.add(debugMesh);

            // Inside your bone loop in createRagdollForSkinnedMesh
            const initialMatrix = bone.matrixWorld.clone();
            bone.userData.initialMatrix = initialMatrix;
          });
        }
      });
      
      // Create constraints between parent and child bones
      bonePhysicsMap.forEach((childObj) => {
        const boneParent = childObj.bone.parent;
        if (boneParent && bonePhysicsMap.has(boneParent.name)) {
          const parentObj = bonePhysicsMap.get(boneParent.name);
          const childPos = new THREE.Vector3();
          childObj.bone.getWorldPosition(childPos);
          const parentPos = new THREE.Vector3();
          boneParent.getWorldPosition(parentPos);
      
          // Define the connection point in parent's coordinate system
          const pivotA = new CANNON.Vec3(
            childPos.x - parentPos.x,
            childPos.y - parentPos.y,
            childPos.z - parentPos.z
          );
          const pivotB = new CANNON.Vec3(0, 0, 0);
          
          // Configure joint type based on bone name
          let constraint;
          
          // Get rotation limits based on bone type - moderate limits to allow natural movement
          const getLimits = (boneName) => {
            if (boneName.includes('Elbow') || boneName.includes('LowerLeg')) {
              // Elbows and knees bend in one direction with moderate limits
              return {
                low: { x: -Math.PI/16, y: -Math.PI/8, z: -Math.PI/8 },
                high: { x: Math.PI/1.5, y: Math.PI/8, z: Math.PI/8 },
                collideConnected: false
              };
            } else if (boneName.includes('Arm')) {
              // Arms need more freedom for natural falling
              return {
                low: { x: -Math.PI/2, y: -Math.PI/4, z: -Math.PI/3 },
                high: { x: Math.PI/2, y: Math.PI/4, z: Math.PI/3 },
                collideConnected: false
              };
            } else if (boneName.includes('Leg') || boneName.includes('UpperLeg')) {
              // Legs need moderate movement for natural falls
              return {
                low: { x: -Math.PI/3, y: -Math.PI/6, z: -Math.PI/6 },
                high: { x: Math.PI/3, y: Math.PI/6, z: Math.PI/6 },
                collideConnected: false
              };
            } else if (boneName.includes('Spine') || boneName.includes('Chest') || boneName.includes('Hips')) {
              // Torso should be stiffer but still bend somewhat naturally
              return {
                low: { x: -Math.PI/6, y: -Math.PI/6, z: -Math.PI/6 },
                high: { x: Math.PI/6, y: Math.PI/6, z: Math.PI/6 },
                collideConnected: false
              };
            } else if (boneName.includes('Neck') || boneName.includes('Head')) {
              // Head should have limited rotation but still natural
              return {
                low: { x: -Math.PI/4, y: -Math.PI/4, z: -Math.PI/4 },
                high: { x: Math.PI/4, y: Math.PI/4, z: Math.PI/4 },
                collideConnected: false
              };
            } else if (boneName.includes('Hand') || boneName.includes('Foot')) {
              // Hands and feet need more freedom
              return {
                low: { x: -Math.PI/3, y: -Math.PI/3, z: -Math.PI/3 },
                high: { x: Math.PI/3, y: Math.PI/3, z: Math.PI/3 },
                collideConnected: false
              };
            } else {
              // Default for other bones
              return {
                low: { x: -Math.PI/4, y: -Math.PI/4, z: -Math.PI/4 },
                high: { x: Math.PI/4, y: Math.PI/4, z: Math.PI/4 },
                collideConnected: false
              };
            }
          };
          
          // Determine if we should use a hinge (elbow/knee) or more complex constraint
          if (childObj.bone.name.includes('Elbow') || childObj.bone.name.includes('LowerLeg')) {
            // For elbows and knees, use hinge constraint with proper axis
            const axisA = new CANNON.Vec3(0, 1, 0); // Rotation axis
            const axisB = new CANNON.Vec3(0, 1, 0);
            
            const limits = getLimits(childObj.bone.name);
            
            constraint = new CANNON.HingeConstraint(parentObj.body, childObj.body, {
              pivotA: pivotA,
              pivotB: pivotB,
              axisA: axisA,
              axisB: axisB,
              // Set limits directly in the constructor
              collideConnected: false,
              maxForce: 5e6, // Increased from 1e6 for more stability
              // Limits in CANNON.js are set with these parameters
              low: limits.low.x,  // Lower limit
              high: limits.high.x // Upper limit
            });
            
          } else {
            // For other joints use a restricted but flexible constraint
            const limits = getLimits(childObj.bone.name);
            
            // Use a more flexible constraint for natural falling
            constraint = new CANNON.PointToPointConstraint(
              parentObj.body,
              pivotA,
              childObj.body,
              pivotB,
              5e4 // Increased from 2e4 for more stability
            );
            
            // Add distance constraints to maintain structure without being too rigid
            if (childObj.bone.name.includes('Spine') || childObj.bone.name.includes('Chest') || 
                childObj.bone.name.includes('Hips')) {
              // Add extra constraint for torso to keep it more intact
              const distConstraint = new CANNON.DistanceConstraint(
                parentObj.body,
                childObj.body,
                pivotA.length() * 1.05, // Reduced stretch from 1.1 to 1.05
                5e4 // Increased from 1e4 for more stability
              );
              world.addConstraint(distConstraint);
              
              // Store for reference
              if (!childObj.extraConstraints) childObj.extraConstraints = [];
              childObj.extraConstraints.push(distConstraint);
            }
            
            // Add distance constraints for all joints to prevent stretching
            // This helps prevent the spaghetti effect
            const distConstraint = new CANNON.DistanceConstraint(
              parentObj.body,
              childObj.body,
              pivotA.length() * 1.02, // Very minimal stretch
              2e4 // Strong but not rigid
            );
            world.addConstraint(distConstraint);
            
            if (!childObj.extraConstraints) childObj.extraConstraints = [];
            childObj.extraConstraints.push(distConstraint);
          }
          
          // Store the constraint on both bodies for reference
          if (!parentObj.constraints) parentObj.constraints = [];
          if (!childObj.constraints) childObj.constraints = [];
          
          parentObj.constraints.push(constraint);
          childObj.constraints.push(constraint);
          
          world.addConstraint(constraint);
          
          // Store the constraint type and limits for use in active posing
          childObj.jointLimits = getLimits(childObj.bone.name);
          childObj.parentBody = parentObj.body;

          // Add a distance constraint between spine and hips to fix the torso in place
          if (childObj.bone.name === 'Spine' && parentObj.bone.name === 'Hips') {
            const spineHipsConstraint = new CANNON.DistanceConstraint(
              parentObj.body,
              childObj.body,
              pivotA.length(),
              1e5 // Very stiff constraint
            );
            world.addConstraint(spineHipsConstraint);
            
            if (!childObj.extraConstraints) childObj.extraConstraints = [];
            childObj.extraConstraints.push(spineHipsConstraint);
          }
          
          // Add a special constraint for the head to neck connection
          if (childObj.bone.name === 'Head' && parentObj.bone.name === 'Neck') {
            const headNeckConstraint = new CANNON.DistanceConstraint(
              parentObj.body,
              childObj.body,
              pivotA.length(),
              1e5 // Very stiff constraint
            );
            world.addConstraint(headNeckConstraint);
            
            if (!childObj.extraConstraints) childObj.extraConstraints = [];
            childObj.extraConstraints.push(headNeckConstraint);
          }
        }
      });
      
      // Store the entire bonePhysicsMap on the bandit
      model.userData.bonePhysicsMap = bonePhysicsMap;
      
      // Store bone groups for balance control
      model.userData.balanceData = {
        spineBones,
        legBones,
        footBones,
        centerOfMass: new THREE.Vector3(),
        isBalancing: false,
        balanceStrength: 0.3
      };

      return bonePhysicsMap;
    };

    // Add this helper function inside your useEffect (or in the same scope as onMouseClick)
    const freezeRagdoll = (bonePhysicsMap) => {
      bonePhysicsMap.forEach((obj) => {
        if (!obj.body.frozen) {
          obj.body.initialMass = obj.body.mass; // Store initial mass
          obj.body.mass = 0; // Make it static
          obj.body.updateMassProperties();
          obj.body.velocity.set(0, 0, 0);
          obj.body.angularVelocity.set(0, 0, 0);
          obj.body.frozen = true;
        }
      });
    };

    const unfreezeRagdoll = (bonePhysicsMap) => {
      // First, store the current relative positions and orientations
      const boneRelativePositions = new Map();
      
      // Gather all relative positions before unfreezing
      bonePhysicsMap.forEach((obj) => {
        if (obj.body.frozen) {
          // Store relative position to parent if available
          if (obj.bone.parent) {
            const localPos = obj.bone.parent.worldToLocal(
              new THREE.Vector3().copy(obj.body.position)
            );
            boneRelativePositions.set(obj.bone.name, {
              position: localPos,
              quaternion: obj.body.quaternion.clone()
            });
          }
        }
      });
      
      // Now unfreeze while maintaining structure
      bonePhysicsMap.forEach((obj) => {
        if (obj.body.frozen) {
          // Store reference state before unfreezing
          if (!obj.body.originalQuaternion) {
            obj.body.originalQuaternion = new CANNON.Quaternion().copy(obj.body.quaternion);
          }
          
          if (!obj.body.originalPosition) {
            obj.body.originalPosition = new CANNON.Vec3().copy(obj.body.position);
          }
          
          // Unfreeze by restoring mass
          obj.body.mass = obj.body.initialMass;
          obj.body.updateMassProperties();
          obj.body.frozen = false;
          
          // Reset velocity and angular velocity to prevent initial impulse
          obj.body.velocity.set(0, 0, 0);
          obj.body.angularVelocity.set(0, 0, 0);
          
          // Ensure physics body matches bone precisely
          const boneWorldPos = new THREE.Vector3();
          obj.bone.getWorldPosition(boneWorldPos);
          
          // Update positions to match bones exactly
          obj.body.position.copy(boneWorldPos);
          
          // Allow small random velocity to make falling look more natural
          const randomVel = 0.1;
          obj.body.velocity.set(
            (Math.random() - 0.5) * randomVel,
            (Math.random() - 0.5) * randomVel,
            (Math.random() - 0.5) * randomVel
          );
          
          // Align debug and hit meshes
          obj.debugMesh.position.copy(boneWorldPos);
          if (obj.hitMesh) {
            obj.hitMesh.position.copy(boneWorldPos);
          }
        }
      });
    };

    // Add balancing system
    const updateRagdollBalance = (bandit, deltaTime) => {
      if (!bandit.userData.balanceData) return;
      
      const { spineBones, legBones, footBones, centerOfMass, balanceStrength } = bandit.userData.balanceData;
      const bonePhysicsMap = bandit.userData.bonePhysicsMap;
      
      if (!bonePhysicsMap) return;
      
      // Calculate current center of mass
      let totalMass = 0;
      let weightedPosition = new THREE.Vector3();
      
      bonePhysicsMap.forEach((physicsObj) => {
        const pos = new THREE.Vector3(
          physicsObj.body.position.x,
          physicsObj.body.position.y,
          physicsObj.body.position.z
        );
        const mass = physicsObj.body.mass;
        totalMass += mass;
        
        // Weight position by mass
        pos.multiplyScalar(mass);
        weightedPosition.add(pos);
      });
      
      // Complete the weighted average
      if (totalMass > 0) {
        weightedPosition.divideScalar(totalMass);
        centerOfMass.copy(weightedPosition);
      }
      
      // Check if we need to balance (e.g., if center of mass is too high)
      let isStanding = false;
      let needsGroundCorrection = false;
      
      // Check if at least one foot is near the ground or we're too low
      footBones.forEach(boneName => {
        if (bonePhysicsMap.has(boneName)) {
          const footPos = bonePhysicsMap.get(boneName).body.position;
          if (footPos.y < 0.5) {
            isStanding = true;
          }
          // If we're below ground level, we need correction
          if (footPos.y < 0.1) {
            needsGroundCorrection = true;
          }
        }
      });
      
      // If we're too low, push everything up
      if (needsGroundCorrection || centerOfMass.y < 0.5) {
        bonePhysicsMap.forEach(physicsObj => {
          const upForce = new CANNON.Vec3(0, 10, 0); // Strong upward force
          physicsObj.body.force.vadd(upForce, physicsObj.body.force);
        });
      }
      
      if (isStanding && centerOfMass.y > 0.5) {
        // Apply forces to help maintain balance
        
        // Apply vertical force to spine to help stay upright
        spineBones.forEach(boneName => {
          if (bonePhysicsMap.has(boneName)) {
            const spineObj = bonePhysicsMap.get(boneName);
            // Increase the upward force for better stability
            const force = new CANNON.Vec3(0, 8 * balanceStrength, 0);
            spineObj.body.force.vadd(force, spineObj.body.force);
            
            // Calculate torque to stay upright
            const currentRot = new THREE.Quaternion(
              spineObj.body.quaternion.x,
              spineObj.body.quaternion.y,
              spineObj.body.quaternion.z,
              spineObj.body.quaternion.w
            );
            
            // Get upright direction
            const upVector = new THREE.Vector3(0, 1, 0);
            const currentUp = new THREE.Vector3(0, 1, 0).applyQuaternion(currentRot);
            
            // Calculate correction torque
            const correctionAxis = new THREE.Vector3().crossVectors(currentUp, upVector);
            const correctionTorque = new CANNON.Vec3(
              correctionAxis.x * 3 * balanceStrength,
              correctionAxis.y * 3 * balanceStrength,
              correctionAxis.z * 3 * balanceStrength
            );
            
            spineObj.body.torque.vadd(correctionTorque, spineObj.body.torque);
          }
        });
        
        // Apply forces to legs to help support weight
        legBones.forEach(boneName => {
          if (bonePhysicsMap.has(boneName)) {
            const legObj = bonePhysicsMap.get(boneName);
            const legPos = legObj.body.position;
            
            // Push legs downward for support, but not below 0.3 units
            if (legPos.y > 0.3) {
              const supportForce = new CANNON.Vec3(0, -2 * balanceStrength, 0);
              legObj.body.force.vadd(supportForce, legObj.body.force);
            } else {
              // If leg is too low, push it up a bit
              const liftForce = new CANNON.Vec3(0, 3, 0);
              legObj.body.force.vadd(liftForce, legObj.body.force);
            }
          }
        });
      }
    };

    // Add function to set a default pose with joint rotations
    const setDefaultPose = (bandit) => {
      // Define the standing pose target rotations
      const standingPose = [
        // Spine and core alignment
        { boneName: 'Spine', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.8 },
        { boneName: 'Hips', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.8 },
        { boneName: 'Chest', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.8 },
        
        // Head position
        { boneName: 'Neck', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.5 },
        { boneName: 'Head', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.5 },
        
        // Arms relaxed at sides
        { boneName: 'LeftUpperArm', targetRotation: new THREE.Euler(0, 0, -0.2), strength: 0.3 },
        { boneName: 'RightUpperArm', targetRotation: new THREE.Euler(0, 0, 0.2), strength: 0.3 },
        { boneName: 'LeftElbow', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.3 },
        { boneName: 'RightElbow', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.3 },
        
        // Legs in standing position
        { boneName: 'LeftUpperLeg', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.6 },
        { boneName: 'RightUpperLeg', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.6 },
        { boneName: 'LeftLowerLeg', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.6 },
        { boneName: 'RightLowerLeg', targetRotation: new THREE.Euler(0, 0, 0), strength: 0.6 },
      ];
      
      bandit.userData.targetPose = standingPose;
      bandit.userData.poseEnabled = true;
      
      // After 5 seconds, switch to a different pose to demonstrate animation
      setTimeout(() => {
        const idlePose = [
          // Slight spine lean
          { boneName: 'Spine', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.5 },
          { boneName: 'Hips', targetRotation: new THREE.Euler(0.05, 0, 0), strength: 0.5 },
          { boneName: 'Chest', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.5 },
          
          // Head slightly tilted
          { boneName: 'Neck', targetRotation: new THREE.Euler(-0.1, 0.2, 0), strength: 0.4 },
          { boneName: 'Head', targetRotation: new THREE.Euler(-0.1, 0.2, 0), strength: 0.4 },
          
          // Arms relaxed but slightly different
          { boneName: 'LeftUpperArm', targetRotation: new THREE.Euler(0, 0, -0.4), strength: 0.3 },
          { boneName: 'RightUpperArm', targetRotation: new THREE.Euler(0, 0, 0.4), strength: 0.3 },
          { boneName: 'LeftElbow', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.3 },
          { boneName: 'RightElbow', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.3 },
          
          // Legs slightly bent
          { boneName: 'LeftUpperLeg', targetRotation: new THREE.Euler(-0.1, 0, 0), strength: 0.5 },
          { boneName: 'RightUpperLeg', targetRotation: new THREE.Euler(-0.1, 0, 0), strength: 0.5 },
          { boneName: 'LeftLowerLeg', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.5 },
          { boneName: 'RightLowerLeg', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.5 },
        ];
        
        bandit.userData.targetPose = idlePose;
        
        // Set up automatic pose cycling for demonstration
        bandit.userData.poseState = 'idle';
        startPoseCycle(bandit);
      }, 5000);
    };
    
    // Function to cycle between different poses for demonstration
    const startPoseCycle = (bandit) => {
      setInterval(() => {
        if (!bandit.userData.poseEnabled) return;
        
        if (bandit.userData.poseState === 'idle') {
          // Switch to a defensive pose
          const defensivePose = [
            // Crouched spine
            { boneName: 'Spine', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.6 },
            { boneName: 'Hips', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.6 },
            { boneName: 'Chest', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.6 },
            
            // Head ducked
            { boneName: 'Neck', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.5 },
            { boneName: 'Head', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.5 },
            
            // Arms up in defensive position
            { boneName: 'LeftUpperArm', targetRotation: new THREE.Euler(-0.5, -0.2, -0.4), strength: 0.4 },
            { boneName: 'RightUpperArm', targetRotation: new THREE.Euler(-0.5, 0.2, 0.4), strength: 0.4 },
            { boneName: 'LeftElbow', targetRotation: new THREE.Euler(1.0, 0, 0), strength: 0.4 },
            { boneName: 'RightElbow', targetRotation: new THREE.Euler(1.0, 0, 0), strength: 0.4 },
            
            // Legs bent in crouch
            { boneName: 'LeftUpperLeg', targetRotation: new THREE.Euler(-0.6, 0, 0), strength: 0.6 },
            { boneName: 'RightUpperLeg', targetRotation: new THREE.Euler(-0.6, 0, 0), strength: 0.6 },
            { boneName: 'LeftLowerLeg', targetRotation: new THREE.Euler(1.2, 0, 0), strength: 0.6 },
            { boneName: 'RightLowerLeg', targetRotation: new THREE.Euler(1.2, 0, 0), strength: 0.6 },
          ];
          
          bandit.userData.targetPose = defensivePose;
          bandit.userData.poseState = 'defensive';
        } else {
          // Return to idle pose
          const idlePose = [
            // Slight spine lean
            { boneName: 'Spine', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.5 },
            { boneName: 'Hips', targetRotation: new THREE.Euler(0.05, 0, 0), strength: 0.5 },
            { boneName: 'Chest', targetRotation: new THREE.Euler(0.1, 0, 0), strength: 0.5 },
            
            // Head slightly tilted
            { boneName: 'Neck', targetRotation: new THREE.Euler(-0.1, 0.2, 0), strength: 0.4 },
            { boneName: 'Head', targetRotation: new THREE.Euler(-0.1, 0.2, 0), strength: 0.4 },
            
            // Arms relaxed but slightly different
            { boneName: 'LeftUpperArm', targetRotation: new THREE.Euler(0, 0, -0.4), strength: 0.3 },
            { boneName: 'RightUpperArm', targetRotation: new THREE.Euler(0, 0, 0.4), strength: 0.3 },
            { boneName: 'LeftElbow', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.3 },
            { boneName: 'RightElbow', targetRotation: new THREE.Euler(0.3, 0, 0), strength: 0.3 },
            
            // Legs slightly bent
            { boneName: 'LeftUpperLeg', targetRotation: new THREE.Euler(-0.1, 0, 0), strength: 0.5 },
            { boneName: 'RightUpperLeg', targetRotation: new THREE.Euler(-0.1, 0, 0), strength: 0.5 },
            { boneName: 'LeftLowerLeg', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.5 },
            { boneName: 'RightLowerLeg', targetRotation: new THREE.Euler(0.2, 0, 0), strength: 0.5 },
          ];
          
          bandit.userData.targetPose = idlePose;
          bandit.userData.poseState = 'idle';
        }
      }, 3000); // Switch every 3 seconds
    };
    
    // Function to apply target pose forces
    const applyTargetPose = (bandit, deltaTime) => {
      if (!bandit.userData.targetPose || !bandit.userData.poseEnabled) return;
      
      const bonePhysicsMap = bandit.userData.bonePhysicsMap;
      if (!bonePhysicsMap) return;
      
      // Apply motor forces to achieve the target pose
      bandit.userData.targetPose.forEach(poseBone => {
        const { boneName, targetRotation, strength } = poseBone;
        
        if (bonePhysicsMap.has(boneName)) {
          const physicsObj = bonePhysicsMap.get(boneName);
          const body = physicsObj.body;
          
          // Skip if the body is frozen
          if (body.frozen) return;
          
          // Convert target rotation to quaternion
          const targetQuat = new THREE.Quaternion().setFromEuler(targetRotation);
          
          // Get current rotation
          const currentQuat = new THREE.Quaternion(
            body.quaternion.x,
            body.quaternion.y,
            body.quaternion.z,
            body.quaternion.w
          );
          
          // Calculate rotational difference
          const diffQuat = new THREE.Quaternion().copy(targetQuat).multiply(
            new THREE.Quaternion().copy(currentQuat).invert()
          );
          
          // Convert to axis-angle representation
          const euler = new THREE.Euler().setFromQuaternion(diffQuat);
          
          // Scale torque based on difference and strength
          const torqueForce = 5.0 * strength;
          const torque = new CANNON.Vec3(
            euler.x * torqueForce,
            euler.y * torqueForce,
            euler.z * torqueForce
          );
          
          // Apply torque to rotate towards the target
          body.torque.vadd(torque, body.torque);
        }
      });
    };

    const animate = () => {
      requestAnimationFrame(animate);
      
      // Calculate delta time for smoother animation
      const deltaTime = 1/120; // Use smaller timestep for more stable physics
      
      // Run multiple substeps for better stability
      const numSubSteps = 3;
      for (let i = 0; i < numSubSteps; i++) {
        world.step(deltaTime / numSubSteps);
      }
    
      // Update bandit overall transform from main physics body
      banditsRef.current.forEach((bandit, index) => {
        const banditBody = banditBodiesRef.current[index];
        if (banditBody) {
          bandit.position.copy(banditBody.position);
          bandit.quaternion.copy(banditBody.quaternion);
        }
    
        // Update hitbox if available
        const hitbox = hitboxesRef.current[index];
        if (hitbox) {
          hitbox.position.copy(bandit.position);
          hitbox.quaternion.copy(bandit.quaternion);
        }
        
        // Only apply pose targeting when frozen or pose enabled
        if (bandit.userData.poseEnabled) {
          applyTargetPose(bandit, deltaTime);
        }
        
        // Apply balancing forces when not fully locked
        updateRagdollBalance(bandit, deltaTime);
    
        // Update each bone using its physics object
        const bonePhysicsMap = bandit.userData.bonePhysicsMap;
        if (bonePhysicsMap) {
          // First update the model matrix to ensure correct bone positions
          bandit.updateMatrixWorld(true);
          
          // Fix all angular velocities to zero each frame for non-frozen bodies
          bonePhysicsMap.forEach(obj => {
            if (!obj.body.frozen) {
              // Limit angular velocity instead of completely resetting it
              const maxAngularVelocity = 2; // Reduced from 3 for more stability
              const angVel = obj.body.angularVelocity;
              const angVelMagnitude = Math.sqrt(
                angVel.x * angVel.x + angVel.y * angVel.y + angVel.z * angVel.z
              );
              
              if (angVelMagnitude > maxAngularVelocity) {
                // Scale down angular velocity if it exceeds the maximum
                const scale = maxAngularVelocity / angVelMagnitude;
                angVel.scale(scale, angVel);
              }
              
              // Reduce torque but don't eliminate it completely
              obj.body.torque.scale(0.7, obj.body.torque); // Increased damping from 0.8
              
              // Apply stronger damping to prevent oscillation
              obj.body.angularDamping = 0.95;
              obj.body.linearDamping = 0.8;
            }
          });
          
          // Update the actual bone positions based on physics
          bonePhysicsMap.forEach((obj) => {
            // Prevent bones from falling through the ground
            if (obj.body.position.y < 0.1) {
              obj.body.position.y = 0.1;
              if (obj.body.velocity.y < 0) {
                obj.body.velocity.y = 0;
              }
              // Add small upward impulse
              obj.body.applyImpulse(
                new CANNON.Vec3(0, 0.5, 0),
                new CANNON.Vec3(0, 0, 0)
              );
            }
            
            if (obj.body.frozen) {
              // When frozen, make physics bodies exactly follow actual bones
              const boneWorldPos = new THREE.Vector3();
              obj.bone.getWorldPosition(boneWorldPos);
              
              // Update physics body position
              obj.body.position.copy(boneWorldPos);
              
              // Update debug & hit mesh positions
              obj.debugMesh.position.copy(boneWorldPos);
              if (obj.hitMesh) {
                obj.hitMesh.position.copy(boneWorldPos);
              }
              
              // Copy bone rotation to physics body
              const worldQuat = new THREE.Quaternion();
              obj.bone.getWorldQuaternion(worldQuat);
              obj.body.quaternion.copy(worldQuat);
              obj.debugMesh.quaternion.copy(worldQuat);
              if (obj.hitMesh) {
                obj.hitMesh.quaternion.copy(worldQuat);
              }
            } else {
              // When moving/ragdolling, update debug mesh from physics body
              obj.debugMesh.position.copy(obj.body.position);
              
              // Allow rotation but prevent extreme deformation
              if (obj.body.originalQuaternion) {
                // Get current rotation - convert to THREE.js quaternion first
                const currentQuat = new THREE.Quaternion(
                  obj.body.quaternion.x,
                  obj.body.quaternion.y, 
                  obj.body.quaternion.z,
                  obj.body.quaternion.w
                );
                
                // Also convert the original quaternion to THREE.js quaternion
                const originalQuat = new THREE.Quaternion(
                  obj.body.originalQuaternion.x,
                  obj.body.originalQuaternion.y,
                  obj.body.originalQuaternion.z,
                  obj.body.originalQuaternion.w
                );
                
                // Check if rotation has become extreme by comparing with original
                const dotProduct = currentQuat.dot(originalQuat);
                
                // If rotation is extreme (dot product too negative), partially correct it
                if (dotProduct < -0.5) {
                  // Create a corrected quaternion that's a blend between current and original
                  const correctedQuat = new THREE.Quaternion();
                  originalQuat.slerp(currentQuat, 0.7, correctedQuat);
                  
                  // Copy back to the CANNON quaternion
                  obj.body.quaternion.x = correctedQuat.x;
                  obj.body.quaternion.y = correctedQuat.y;
                  obj.body.quaternion.z = correctedQuat.z;
                  obj.body.quaternion.w = correctedQuat.w;
                }
              }
              
              // Update visual elements with actual physics state
              obj.debugMesh.quaternion.copy(obj.body.quaternion);
              
              // Update hit mesh if it exists
              if (obj.hitMesh) {
                obj.hitMesh.position.copy(obj.body.position);
                obj.hitMesh.quaternion.copy(obj.body.quaternion);
              }
              
              // Update visual bone from physics body (position and rotation)
              if (obj.bone.parent) {
                obj.bone.parent.updateMatrixWorld();
                
                // Convert physics body position to bone's local space
                const localPos = obj.bone.parent.worldToLocal(
                  new THREE.Vector3(obj.body.position.x, obj.body.position.y, obj.body.position.z)
                );
                
                // Update position
                obj.bone.position.copy(localPos);
                
                // Update rotation - allow physics to drive bone rotation
                // Create a local quaternion that represents the rotation in parent space
                const parentWorldQuat = new THREE.Quaternion();
                obj.bone.parent.getWorldQuaternion(parentWorldQuat);
                const worldQuat = new THREE.Quaternion(
                  obj.body.quaternion.x,
                  obj.body.quaternion.y,
                  obj.body.quaternion.z,
                  obj.body.quaternion.w
                );
                
                // Calculate the local quaternion
                const parentInverse = parentWorldQuat.clone().invert();
                const localQuat = worldQuat.clone().premultiply(parentInverse);
                
                // Apply local quaternion to bone
                obj.bone.quaternion.copy(localQuat);
              } else {
                // For root bones without parents
                obj.bone.position.set(obj.body.position.x, obj.body.position.y, obj.body.position.z);
                obj.bone.quaternion.copy(obj.body.quaternion);
              }
            }
          });
        }
      });
    
      // Update skull icon positions (existing code)
      skullIconsRef.current.forEach(({ sprite, banditIndex }) => {
        const banditBody = banditBodiesRef.current[banditIndex];
        sprite.position.set(banditBody.position.x, banditBody.position.y + 2, banditBody.position.z);
      });
    
      if (camera.position.y < 1) {
        camera.position.y = 1;
      }
    
      controls.update();
      renderer.render(scene, camera);
    };
    
    animate();

    return () => {
      window.removeEventListener('pointerdown', onMouseClick);
      window.removeEventListener('mousemove', onMouseMove);
      mountRef.current.removeChild(renderer.domElement);
    };
  }, [volume]);

  const handleLeaveArea = () => {
    history.push('/looting');
  };

  // Update the createBloodSplatterSprite function to use the animation frames
  const createBloodSplatterSprite = (position) => {
    // Create a group to hold the animated sprite
    const spriteGroup = new THREE.Group();
    spriteGroup.position.set(
      position.x + (Math.random() * 0.2 - 0.1), 
      position.y + (Math.random() * 0.2), 
      position.z + (Math.random() * 0.2 - 0.1)
    );
    
    // Randomize scale for variety
    const scale = 0.5 + Math.random() * 0.5;
    
    // Create a texture loader
    const textureLoader = new THREE.TextureLoader();
    
    // Load the first frame to start with
    const initialTexture = textureLoader.load(bloodSplatterFrames[0]);
    const spriteMaterial = new THREE.SpriteMaterial({ 
      map: initialTexture,
      transparent: true,
      alphaTest: 0.1,
      opacity: 0.9,
      depthTest: true,
      depthWrite: false,
      blending: THREE.NormalBlending
    });
    
    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.scale.set(scale, scale, scale);
    
    // Randomize rotation for variety
    sprite.material.rotation = Math.random() * Math.PI * 2;
    
    spriteGroup.add(sprite);
    
    // Set up animation
    let currentFrame = 0;
    const frameDuration = 50; // milliseconds per frame
    
    const animateBloodSplatter = () => {
      currentFrame++;
      
      if (currentFrame < bloodSplatterFrames.length) {
        // Load the next frame
        textureLoader.load(bloodSplatterFrames[currentFrame], (texture) => {
          sprite.material.map = texture;
          sprite.material.needsUpdate = true;
          
          // Schedule the next frame
          setTimeout(animateBloodSplatter, frameDuration);
        });
      } else {
        // Animation complete - fade out the sprite
        const fadeOutDuration = 500; // milliseconds
        const fadeStep = sprite.material.opacity / (fadeOutDuration / 30); // 30ms per fade step
        
        const fadeOut = () => {
          if (sprite.material.opacity > 0) {
            sprite.material.opacity -= fadeStep;
            setTimeout(fadeOut, 30);
          } else {
            // Remove the sprite when fully faded
            spriteGroup.remove(sprite);
            sprite.material.dispose();
            sprite.geometry.dispose();
          }
        };
        
        fadeOut();
      }
    };
    
    // Start the animation
    setTimeout(animateBloodSplatter, frameDuration);
    
    return spriteGroup;
  };

  return (
    <div ref={mountRef} className="wasteland-container">
      <ParticleSystem ref={particleSystemRef} scene={sceneRef.current} />
      {remainingBandits === 0 && (
        <button onClick={handleLeaveArea} className="leave-area-button">
          Leave area
        </button>
      )}
      <div id="debug" style={{
        position: 'absolute', 
        bottom: '20px', 
        left: '20px', 
        background: 'rgba(0,0,0,0.7)',
        color: 'white',
        padding: '10px',
        fontFamily: 'monospace',
        borderRadius: '5px',
        zIndex: 100
      }}></div>
    </div>
  );
};

export default Wasteland;