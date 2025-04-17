import React, { useEffect, useRef, useState } from 'react';
import { useHistory } from 'react-router-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { SkeletonHelper } from 'three'; // Add import for SkeletonHelper
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

const Wasteland = ({ volume }) => {
  const mountRef = useRef(null);
  const cameraRef = useRef(null);
  const [remainingBandits, setRemainingBandits] = useState(1);
  const [showHitboxes, setShowHitboxes] = useState(true);
  const [showDebugMenu, setShowDebugMenu] = useState(false); // State for showing/hiding debug menu
  const [showSkeleton, setShowSkeleton] = useState(false); // State for showing/hiding skeleton
  const banditsRef = useRef([]);
  const hitboxesRef = useRef([]);
  const skullIconsRef = useRef([]);
  const hitBanditsRef = useRef(new Set());
  const skeletonHelpersRef = useRef([]); // Reference to store skeleton helpers
  const meshPhysicsBodiesRef = useRef([]);
  const meshPartsRef = useRef([]);
  const physicsConstraintsRef = useRef([]);
  const bonePhysicsBodiesRef = useRef([]);
  
  // References for dragging functionality
  const dragConstraintRef = useRef(null);
  const draggedBodyRef = useRef(null);
  const dragPlaneRef = useRef(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0));
  
  // Create references for physics world and drag helper
  const worldRef = useRef(null);
  const dragHelperRef = useRef(null);
  
  // Create a reference for the camera controls
  const controlsRef = useRef(null);
  
  // Create a direct reference to track visibility state outside of React state
  const hitboxVisibleRef = useRef(false);
  const skeletonVisibleRef = useRef(false);

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
    controlsRef.current = controls; // Store controls in ref
    controls.enableDamping = true; // Enable damping (inertia)
    controls.dampingFactor = 0.25; // Damping factor
    controls.screenSpacePanning = false; // Disable panning
    controls.enableZoom = true; // Enable zooming
    controls.enablePan = true; // Enable panning
    
    // Configure controls to use right mouse button for rotation
    controls.mouseButtons = {
      RIGHT: THREE.MOUSE.ROTATE, // Right mouse for camera rotation
      MIDDLE: THREE.MOUSE.DOLLY, // Middle mouse for zoom
      LEFT: THREE.MOUSE.NONE     // Disable left mouse for camera (we'll use it for shooting)
    };

    const world = new CANNON.World();
    world.gravity.set(0, -25, 0); // Set gravity
    
    // Store world in ref for access outside useEffect
    worldRef.current = world;

    // Create ground material with higher friction
    const groundMaterial = new CANNON.Material('groundMaterial');
    groundMaterial.friction = 0.6; // Reduced from 0.8 to allow easier sliding when hit
    groundMaterial.restitution = 0.2; // Some bounce, but not too much

    const groundBody = new CANNON.Body({
      mass: 0, // Mass of 0 makes the body static
      shape: new CANNON.Plane(),
      material: groundMaterial
    });
    groundBody.quaternion.setFromEuler(-Math.PI / 2, 0, 0);
    world.addBody(groundBody);

    // Add invisible walls around play area to prevent parts from flying too far
    const wallThickness = 1;
    const wallHeight = 50;
    const arenaSize = 30;
    
    // Create wall material with high friction to stop rolling parts
    const wallMaterial = new CANNON.Material('wallMaterial');
    wallMaterial.friction = 0.8;
    wallMaterial.restitution = 0.2;
    
    // Create 4 walls
    const walls = [];
    
    // Front wall
    walls.push(new CANNON.Body({
      mass: 0,
      shape: new CANNON.Box(new CANNON.Vec3(arenaSize, wallHeight, wallThickness)),
      position: new CANNON.Vec3(0, wallHeight, arenaSize),
      material: wallMaterial
    }));
    
    // Back wall
    walls.push(new CANNON.Body({
      mass: 0,
      shape: new CANNON.Box(new CANNON.Vec3(arenaSize, wallHeight, wallThickness)),
      position: new CANNON.Vec3(0, wallHeight, -arenaSize),
      material: wallMaterial
    }));
    
    // Left wall
    walls.push(new CANNON.Body({
      mass: 0,
      shape: new CANNON.Box(new CANNON.Vec3(wallThickness, wallHeight, arenaSize)),
      position: new CANNON.Vec3(-arenaSize, wallHeight, 0),
      material: wallMaterial
    }));
    
    // Right wall
    walls.push(new CANNON.Body({
      mass: 0,
      shape: new CANNON.Box(new CANNON.Vec3(wallThickness, wallHeight, arenaSize)),
      position: new CANNON.Vec3(arenaSize, wallHeight, 0),
      material: wallMaterial
    }));
    
    // Add all walls to world
    walls.forEach(wall => {
      world.addBody(wall);
    });

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
    loader.load('https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/alternative_2/frontend/media/69backup.glb', (gltf) => {
      console.log('📦 Model loaded');
      
      for (let i = 0; i < 1; i++) {
        const bandit = gltf.scene.clone();
        
        // Log the structure of the model
        console.log('📋 Model structure:');
        
        // First collect all meshes that aren't part of the skeleton
        const meshParts = [];
        bandit.traverse((child) => {
          if (child.type && child.name) {
            console.log(`➤ ${child.type}: ${child.name}`);
          }
          if (child.isMesh && !child.isSkinnedMesh) {
            console.log(`  ▪ Found mesh part: ${child.name}`);
            meshParts.push(child);
          }
          if (child.isSkinnedMesh) {
            console.log(`  ▪ Bones: ${child.skeleton.bones.length}`);
          }
        });
        
        // Create physics bodies for mesh parts
        meshParts.forEach(mesh => {
          // Calculate bounding box for mesh
          if (!mesh.geometry.boundingBox) {
            mesh.geometry.computeBoundingBox();
          }
          
          const boundingBox = mesh.geometry.boundingBox;
          const size = new THREE.Vector3();
          boundingBox.getSize(size);
          
          // Create slightly smaller box for better collision
          const halfSize = new CANNON.Vec3(
            size.x * 0.4, 
            size.y * 0.4, 
            size.z * 0.4
          );
          
          // Get world position of mesh
          const worldPosition = new THREE.Vector3();
          mesh.getWorldPosition(worldPosition);
          
          // Determine mass based on body part (heavier core, lighter limbs)
          let partMass = 2; // Default mass
          if (mesh.name.includes("Hips") || mesh.name.includes("Chest")) {
            partMass = 3; // Heavier torso
          } else if (mesh.name.includes("Head")) {
            partMass = 2.5; // Slightly heavier head
          } else if (mesh.name.includes("Foot") || mesh.name.includes("Hand")) {
            partMass = 1; // Lighter extremities
          } else if (mesh.name.includes("Arm") || mesh.name.includes("Leg")) {
            partMass = 1.5; // Medium weight limbs
          }
          
          // Create physics body
          const body = new CANNON.Body({
            mass: partMass, // Mass varies by body part
            position: new CANNON.Vec3(
              worldPosition.x,
              worldPosition.y,
              worldPosition.z
            ),
            shape: new CANNON.Box(halfSize),
            material: new CANNON.Material({
              friction: 0.4, // Increased friction
              restitution: 0.25 // Slight increase in bounce
            })
          });
          
          // Create contact material between body parts and ground to prevent rolling
          const bodyGroundContactMaterial = new CANNON.ContactMaterial(
            body.material, 
            groundMaterial, 
            {
              friction: 0.5, // Reduced from 0.7 for easier movement on ground
              restitution: 0.15, // Slightly higher bounce on ground contact
              contactEquationStiffness: 1e7, // Reduced to make ground contact less rigid
              contactEquationRelaxation: 4 // More relaxation for smoother movement
            }
          );
          world.addContactMaterial(bodyGroundContactMaterial);
          
          // Freeze body initially so it doesn't fall right away
          body.initialMass = body.mass;
          body.mass = 0; // Makes it static
          body.updateMassProperties();
          body.velocity.set(0, 0, 0);
          body.angularVelocity.set(0, 0, 0);
          body.isFrozen = true; // Custom property to track frozen state
          
          // Store body's initial position for better resets
          body.initialPosition = new CANNON.Vec3(
            worldPosition.x,
            worldPosition.y,
            worldPosition.z
          );
          
          // Add to world
          world.addBody(body);
          
          // Store reference for later
          meshPhysicsBodiesRef.current.push(body);
          meshPartsRef.current.push({
            mesh: mesh,
            body: body
          });
          
          console.log(`🧱 Created physics body for ${mesh.name}`);
        });
        
        // Now find all bones and map them to meshes
        const bones = [];
        const boneToMeshMap = new Map();
        
        // Find all bones in the model
        bandit.traverse(node => {
          if (node.isBone) {
            bones.push(node);
            console.log(`🦴 Found bone: ${node.name}`);
            
            // Try to find matching mesh
            const matchingMesh = meshParts.find(mesh => {
              // Try different naming patterns
              const meshBaseName = mesh.name.replace("_Mesh", "");
              return meshBaseName === node.name || mesh.name === node.name;
            });
            
            if (matchingMesh) {
              boneToMeshMap.set(node, matchingMesh);
              console.log(`🔗 Matched bone ${node.name} with mesh ${matchingMesh.name}`);
            } else {
              console.log(`⚠️ No matching mesh found for bone ${node.name}`);
            }
          }
        });
        
        // Define bone connections (parent-child relationships)
        const boneConnections = [
          { parent: "Hips", children: ["RightUpperLeg", "LeftUpperLeg", "Chest"] },
          { parent: "Chest", children: ["Head", "RightUpperArm", "LeftUpperArm"] },
          { parent: "RightUpperLeg", children: ["RightLowerLeg"] },
          { parent: "RightLowerLeg", children: ["RightFoot"] },
          { parent: "LeftUpperLeg", children: ["LeftLowerLeg"] },
          { parent: "LeftLowerLeg", children: ["LeftFoot"] },
          { parent: "RightUpperArm", children: ["RightElbow"] },
          { parent: "RightElbow", children: ["RightHand"] },
          { parent: "LeftUpperArm", children: ["LeftElbow"] },
          { parent: "LeftElbow", children: ["LeftHand"] }
        ];
        
        // Function to get physics body for a mesh
        const getPhysicsBodyForMesh = (mesh) => {
          const physicsInfo = meshPartsRef.current.find(item => item.mesh === mesh);
          return physicsInfo ? physicsInfo.body : null;
        };
        
        // Create constraints between connected parts
        boneConnections.forEach(connection => {
          const parentBone = bones.find(bone => bone.name === connection.parent);
          if (!parentBone) {
            console.log(`⚠️ Could not find parent bone ${connection.parent}`);
            return;
          }
          
          const parentMesh = boneToMeshMap.get(parentBone);
          if (!parentMesh) {
            console.log(`⚠️ No mesh found for parent bone ${connection.parent}`);
            return;
          }
          
          const parentBody = getPhysicsBodyForMesh(parentMesh);
          if (!parentBody) {
            console.log(`⚠️ No physics body for parent mesh ${parentMesh.name}`);
            return;
          }
          
          // Connect to each child
          connection.children.forEach(childName => {
            const childBone = bones.find(bone => bone.name === childName);
            if (!childBone) {
              console.log(`⚠️ Could not find child bone ${childName}`);
              return;
            }
            
            const childMesh = boneToMeshMap.get(childBone);
            if (!childMesh) {
              console.log(`⚠️ No mesh found for child bone ${childName}`);
              return;
            }
            
            const childBody = getPhysicsBodyForMesh(childMesh);
            if (!childBody) {
              console.log(`⚠️ No physics body for child mesh ${childMesh.name}`);
              return;
            }
            
            // Calculate connection point (position difference between parent and child)
            const parentPos = new THREE.Vector3();
            parentMesh.getWorldPosition(parentPos);
            
            const childPos = new THREE.Vector3();
            childMesh.getWorldPosition(childPos);
            
            // Position difference in parent's local space
            const pivotA = new CANNON.Vec3(
              childPos.x - parentPos.x,
              childPos.y - parentPos.y,
              childPos.z - parentPos.z
            );
            
            // Local to child
            const pivotB = new CANNON.Vec3(0, 0, 0);
            
            // Create constraint
            let constraint;
            
            // Choose constraint type based on joint name
            if (childName.includes("Elbow") || childName.includes("LowerLeg")) {
              // Use hinge for elbows and knees
              const axisA = new CANNON.Vec3(0, 0, 1); // Rotation axis
              const axisB = new CANNON.Vec3(0, 0, 1);
              
              // Set angle limits based on joint type
              let lower = 0; // Minimum angle (radians)
              let upper = Math.PI * 0.75; // Maximum angle (radians)
              
              // Different limits based on joint type
              if (childName.includes("Elbow")) {
                // Elbows have different range of motion
                lower = -Math.PI * 0.1; // Slight hyperextension
                upper = Math.PI * 0.8; // Almost full bend
                
                // Use proper anatomical axis for elbow rotation
                axisA.set(1, 0, 0); // X-axis rotation for elbow bending
                axisB.set(1, 0, 0); // Same axis for child body
              } else if (childName.includes("LowerLeg")) {
                // Special handling for knees - much more restricted than before
                // Knees have very limited movement with proper axis aligned to anatomical movement
                lower = 0; // No hyperextension for knees
                upper = Math.PI * 0.4; // Reduce maximum bend to realistic value (72 degrees)
                
                // Use specific axis that matches anatomical knee bending direction
                // This prevents side-to-side motion and only allows bending in one plane
                axisA.set(1, 0, 0); // X-axis rotation for proper knee bending plane
                axisB.set(1, 0, 0); // Same axis for child body
              }
              
              constraint = new CANNON.HingeConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: axisA,
                axisB: axisB,
                collideConnected: false,
                maxForce: 1800, // Even stronger joints for knees
                // Set the limits directly in the constructor
                low: lower,  // Lower angle limit
                high: upper  // Upper angle limit
              });
              
              // Extra stabilization for hinged joints
              if (childName.includes("LowerLeg")) {
                childBody.angularDamping = 0.95; // Very high angular damping for knees
                childBody.linearDamping = 0.85; // Higher linear damping as well
                
                // Add additional constraints to prevent inward/outward knee movement
                // These side constraints stabilize the knee joint from lateral movement
                
                // Left side constraint - prevents inward movement
                const leftGuide = new CANNON.PointToPointConstraint(
                  parentBody,
                  new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z - 0.15), // Left side of joint 
                  childBody, 
                  new CANNON.Vec3(0, 0, -0.15), // Left side of child
                  2000 // Very strong force
                );
                
                // Right side constraint - prevents outward movement
                const rightGuide = new CANNON.PointToPointConstraint(
                  parentBody,
                  new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z + 0.15), // Right side of joint
                  childBody,
                  new CANNON.Vec3(0, 0, 0.15), // Right side of child
                  2000 // Very strong force
                );
                
                // Simplified track constraints - use higher forces but fewer constraints
                // This works better across different CANNON.js versions
                const sideGuide = new CANNON.PointToPointConstraint(
                  parentBody,
                  new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z + 0.2), // Side of joint
                  childBody,
                  new CANNON.Vec3(0, 0, 0.2), // Side of child
                  2500 // Very strong force - increased from previous version
                );
                
                // Add constraints to world
                world.addConstraint(leftGuide);
                world.addConstraint(rightGuide);
                world.addConstraint(sideGuide);
                
                // Store these auxiliary constraints for cleanup
                [leftGuide, rightGuide, sideGuide].forEach(constraint => {
                  physicsConstraintsRef.current.push({
                    constraint: constraint,
                    parentBody: parentBody,
                    childBody: childBody,
                    parentName: connection.parent,
                    childName: childName,
                    broken: false,
                    isDistanceConstraint: false,
                    isAuxiliaryConstraint: true,
                    isKneeStabilizer: true // Mark as knee stabilizer
                  });
                });
                
                // Force proper rotation by modifying the rotational properties directly
                // Lock rotation except around X-axis by setting extreme angular factors
                if (childBody.angularFactor) {
                  childBody.angularFactor.set(1, 0.01, 0.01); // Allow X rotation, heavily restrict Y and Z
                } else {
                  // Alternative approach if angularFactor property doesn't exist
                  // Use angularDamping for specific axes instead
                  childBody.fixedRotation = false;
                  childBody.updateMassProperties();
                  
                  // Apply extreme torque to counteract any Y or Z rotation
                  // This will be applied in the animation loop
                  childBody.additionalKneeCorrection = true;
                }
                
                // Add extreme damping for unwanted axes of rotation
                // This helps prevent wobbling around Y and Z axes
                childBody.angularDamping = 0.9; // General damping
                
                // Also modify parent (upper leg) to reduce unwanted movements
                if (parentBody.angularFactor) {
                  parentBody.angularFactor.set(1, 0.1, 0.1); // Mostly X-axis rotation
                }
                
                // Apply additional tweaks to the physics parameters to ensure knee stability
                childBody.sleepSpeedLimit = 0.1; // Lower sleep threshold for stability
                childBody.sleepTimeLimit = 0.5; // Quicker sleep for stability when at rest
              } 
              // Similar improved constraints for elbows
              else if (childName.includes("Elbow")) {
                childBody.angularDamping = 0.9; // High angular damping for elbows
                childBody.linearDamping = 0.8; // Higher linear damping for stability
                
                // Add side constraints to prevent lateral elbow movement
                // Front constraint
                const frontGuide = new CANNON.PointToPointConstraint(
                  parentBody,
                  new CANNON.Vec3(pivotA.x, pivotA.y + 0.15, pivotA.z), // Front of joint
                  childBody, 
                  new CANNON.Vec3(0, 0.15, 0), // Front of child
                  1800 // Strong force
                );
                
                // Back constraint
                const backGuide = new CANNON.PointToPointConstraint(
                  parentBody,
                  new CANNON.Vec3(pivotA.x, pivotA.y - 0.15, pivotA.z), // Back of joint
                  childBody,
                  new CANNON.Vec3(0, -0.15, 0), // Back of child
                  1800 // Strong force
                );
                
                // Add constraints to world
                world.addConstraint(frontGuide);
                world.addConstraint(backGuide);
                
                // Store these auxiliary constraints for cleanup
                [frontGuide, backGuide].forEach(constraint => {
                  physicsConstraintsRef.current.push({
                    constraint: constraint,
                    parentBody: parentBody,
                    childBody: childBody,
                    parentName: connection.parent,
                    childName: childName,
                    broken: false,
                    isDistanceConstraint: false,
                    isAuxiliaryConstraint: true,
                    isElbowStabilizer: true
                  });
                });
                
                // Force proper rotation similar to knees
                if (childBody.angularFactor) {
                  childBody.angularFactor.set(1, 0.05, 0.05); // Allow X rotation, restrict Y and Z but less than knees
                }
                
                // Apply additional damping
                childBody.angularDamping = 0.85;
                
                // Also modify parent (upper arm) for better behavior
                if (parentBody.angularFactor) {
                  parentBody.angularFactor.set(1, 0.3, 0.3); // More freedom than legs
                }
              }
            } else if (childName.includes("Foot")) {
              // Special constraint for ankles - limited multi-axis movement with improved stability
              const ankleAxis = new CANNON.Vec3(0, 1, 0);
              
              constraint = new CANNON.ConeTwistConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: ankleAxis,
                axisB: ankleAxis,
                angle: Math.PI * 0.15, // Limited ankle movement
                twistAngle: Math.PI * 0.1 // Limited rotation
              });
              
              // Add stabilizing constraints for ankle
              // Side constraint - prevents excessive lateral movement
              const ankleStabilizer = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z + 0.1), // Side of joint
                childBody,
                new CANNON.Vec3(0, 0, 0.1), // Side of child
                1500 // Strong force
              );
              
              world.addConstraint(ankleStabilizer);
              
              // Store this auxiliary constraint for cleanup
              physicsConstraintsRef.current.push({
                constraint: ankleStabilizer,
                parentBody: parentBody,
                childBody: childBody,
                parentName: connection.parent,
                childName: childName,
                broken: false,
                isDistanceConstraint: false,
                isAuxiliaryConstraint: true,
                isAnkleStabilizer: true
              });
              
              // Restrict foot rotation with angular factors
              if (childBody.angularFactor) {
                childBody.angularFactor.set(0.3, 0.3, 0.5); // Very limited rotation
              }
              
              // Add high damping to prevent foot wobble
              childBody.angularDamping = 0.9;
              childBody.linearDamping = 0.8;
            } else if (childName.includes("UpperArm")) {
              // Improved shoulder joint with restricted movement and better anatomical constraints
              
              // Base constraint - core shoulder movement
              const shoulderAxis = new CANNON.Vec3(0, 1, 0);
              
              constraint = new CANNON.ConeTwistConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: shoulderAxis,
                axisB: shoulderAxis,
                angle: Math.PI * 0.5, // Shoulder can move in a cone but not full 360
                twistAngle: Math.PI * 0.4 // Allow some rotation but not full
              });
              
              // Add forward/backward limiter to prevent unnatural arm positions
              // Front constraint
              const frontLimit = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x + 0.15, pivotA.y, pivotA.z), // Front of shoulder
                childBody,
                new CANNON.Vec3(0.15, 0, 0), // Front of upper arm
                800 // Medium force to allow movement but prevent extremes
              );
              
              world.addConstraint(frontLimit);
              
              // Store auxiliary constraints for cleanup
              physicsConstraintsRef.current.push({
                constraint: frontLimit,
                parentBody: parentBody,
                childBody: childBody,
                parentName: connection.parent,
                childName: childName,
                broken: false,
                isDistanceConstraint: false,
                isAuxiliaryConstraint: true,
                isShoulderStabilizer: true
              });
              
              // Add a supplementary hinge constraint to better control arm rotation
              const armAxis = new CANNON.Vec3(0, 0, 1); // Z-axis for shoulder rotation
              const shoulderHinge = new CANNON.HingeConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: armAxis,
                axisB: armAxis,
                collideConnected: false,
                maxForce: 600, // Light enough to allow shoulder movement
                // Wide limits to not restrict the ConeTwist constraint too much
                low: -Math.PI * 0.6,
                high: Math.PI * 0.6
              });
              
              world.addConstraint(shoulderHinge);
              
              // Store this auxiliary constraint for cleanup
              physicsConstraintsRef.current.push({
                constraint: shoulderHinge,
                parentBody: parentBody,
                childBody: childBody,
                parentName: connection.parent,
                childName: childName,
                broken: false,
                isDistanceConstraint: false,
                isAuxiliaryConstraint: true,
                isShoulderStabilizer: true
              });
              
              // Add damping for smoother arm movement
              childBody.angularDamping = 0.7; // Medium damping for natural arm movement
              childBody.linearDamping = 0.6;
            } else if (childName.includes("UpperLeg")) {
              // Improved hip joint with more anatomical constraints and stability
              const hipAxis = new CANNON.Vec3(0, 1, 0);
              
              // Hip joint with restricted movement
              constraint = new CANNON.ConeTwistConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: hipAxis,
                axisB: hipAxis,
                angle: Math.PI * 0.45, // Hip mobility slightly less than shoulder
                twistAngle: Math.PI * 0.25 // Limited twist
              });
              
              // Add a supplementary hinge constraint to better control leg rotation
              // This creates a more stable knee rotation axis
              const legAxis = new CANNON.Vec3(1, 0, 0); // Match knee axis
              const upperLegHinge = new CANNON.HingeConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: legAxis,
                axisB: legAxis,
                collideConnected: false,
                maxForce: 800, // Strong enough to guide but not override primary constraint
                // Wide limits to not restrict the ConeTwist constraint too much
                low: -Math.PI * 0.5,
                high: Math.PI * 0.5
              });
              
              // Add a forward limiter to prevent legs from going too far forward
              const forwardLimit = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x + 0.1, pivotA.y, pivotA.z), // Front of hip
                childBody,
                new CANNON.Vec3(0.1, 0, 0), // Front of upper leg
                1000 // Medium-strong force
              );
              
              world.addConstraint(upperLegHinge);
              world.addConstraint(forwardLimit);
              
              // Store these auxiliary constraints for cleanup
              [upperLegHinge, forwardLimit].forEach(constraint => {
                physicsConstraintsRef.current.push({
                  constraint: constraint,
                  parentBody: parentBody,
                  childBody: childBody,
                  parentName: connection.parent,
                  childName: childName,
                  broken: false,
                  isDistanceConstraint: false,
                  isAuxiliaryConstraint: true,
                  isHipStabilizer: true
                });
              });
              
              // Add extra damping to upper legs
              childBody.angularDamping = 0.8;
              
              // Add rotation restriction for upper legs 
              if (childBody.angularFactor) {
                childBody.angularFactor.set(1, 0.3, 0.3); // Allow X rotation with some Y/Z
              }
            } else if (childName.includes("Head")) {
              // Improved neck joint with better anatomical constraints
              const neckAxis = new CANNON.Vec3(0, 1, 0);
              
              // Neck joint with very limited movement
              constraint = new CANNON.ConeTwistConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: neckAxis,
                axisB: neckAxis,
                angle: Math.PI * 0.2, // Limited head tilt
                twistAngle: Math.PI * 0.3 // Some head rotation
              });
              
              // Add stabilizing constraints to prevent excessive head movement
              // Left side constraint
              const leftNeckGuide = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z - 0.1), // Left side of neck
                childBody,
                new CANNON.Vec3(0, 0, -0.1), // Left side of head base
                1200 // Medium-strong force
              );
              
              // Right side constraint
              const rightNeckGuide = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z + 0.1), // Right side of neck
                childBody,
                new CANNON.Vec3(0, 0, 0.1), // Right side of head base
                1200 // Medium-strong force
              );
              
              world.addConstraint(leftNeckGuide);
              world.addConstraint(rightNeckGuide);
              
              // Store these auxiliary constraints for cleanup
              [leftNeckGuide, rightNeckGuide].forEach(constraint => {
                physicsConstraintsRef.current.push({
                  constraint: constraint,
                  parentBody: parentBody,
                  childBody: childBody,
                  parentName: connection.parent,
                  childName: childName,
                  broken: false,
                  isDistanceConstraint: false,
                  isAuxiliaryConstraint: true,
                  isNeckStabilizer: true
                });
              });
              
              // Restrict head rotation with angular factors for more natural movement
              if (childBody.angularFactor) {
                childBody.angularFactor.set(0.3, 1, 0.3); // Mostly Y-axis rotation (side to side)
              }
              
              // Add high damping to prevent excessive head bobble
              childBody.angularDamping = 0.9;
              childBody.linearDamping = 0.85;
            } else if (childName.includes("Hand")) {
              // Special constraint for wrists - limited rotation with anatomical constraints
              const wristAxis = new CANNON.Vec3(0, 0, 1); // Z-axis for wrist rotation
              
              // Create specialized constraint for natural wrist movement
              constraint = new CANNON.ConeTwistConstraint(parentBody, childBody, {
                pivotA: pivotA,
                pivotB: pivotB,
                axisA: wristAxis,
                axisB: wristAxis,
                angle: Math.PI * 0.25, // Limited wrist tilt
                twistAngle: Math.PI * 0.5 // Moderate rotation for wrist
              });
              
              // Add stabilizing constraints to prevent unnatural hand movement
              // Side constraint to prevent excessive lateral movement
              const sideHandGuide = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x, pivotA.y, pivotA.z + 0.08), // Side of wrist
                childBody,
                new CANNON.Vec3(0, 0, 0.08), // Side of hand
                1000 // Medium-strong force
              );
              
              // Top constraint to limit up/down motion
              const topHandGuide = new CANNON.PointToPointConstraint(
                parentBody,
                new CANNON.Vec3(pivotA.x, pivotA.y + 0.08, pivotA.z), // Top of wrist
                childBody,
                new CANNON.Vec3(0, 0.08, 0), // Top of hand
                1000 // Medium-strong force
              );
              
              world.addConstraint(sideHandGuide);
              world.addConstraint(topHandGuide);
              
              // Store these auxiliary constraints for cleanup
              [sideHandGuide, topHandGuide].forEach(constraint => {
                physicsConstraintsRef.current.push({
                  constraint: constraint,
                  parentBody: parentBody,
                  childBody: childBody,
                  parentName: connection.parent,
                  childName: childName,
                  broken: false,
                  isDistanceConstraint: false,
                  isAuxiliaryConstraint: true,
                  isHandStabilizer: true
                });
              });
              
              // Restrict hand rotation for natural movement
              if (childBody.angularFactor) {
                childBody.angularFactor.set(0.5, 0.5, 1); // Mostly Z-axis rotation (twist)
              }
              
              // Add moderate damping for natural hand movement
              childBody.angularDamping = 0.8;
              childBody.linearDamping = 0.7;
              
              // Apply specific break threshold adjustment
              physicsConstraintsRef.current.forEach(info => {
                if (info.childName === childName && !info.isAuxiliaryConstraint) {
                  info.customBreakThreshold = 1.3; // Slightly easier to break than default
                }
              });
            } else {
              // Use point-to-point for other joints
              constraint = new CANNON.PointToPointConstraint(
                parentBody,
                pivotA,
                childBody,
                pivotB,
                1200 // Stronger joints
              );
              
              // Add a distance constraint as well to keep parts at proper distance
              const distance = new THREE.Vector3(
                pivotA.x, pivotA.y, pivotA.z
              ).length();
              
              const distConstraint = new CANNON.DistanceConstraint(
                parentBody, 
                childBody, 
                distance,
                600 // Strong force to maintain distance
              );
              
              world.addConstraint(distConstraint);
              
              // Store constraint for cleanup
              physicsConstraintsRef.current.push({
                constraint: distConstraint,
                parentBody: parentBody,
                childBody: childBody,
                parentName: connection.parent,
                childName: childName,
                broken: false,
                isDistanceConstraint: true
              });
            }
            
            // Add damping to reduce oscillation - adjust based on body part
            const isDampingHigh = childName.includes("Head") || connection.parent.includes("Hips");
            parentBody.linearDamping = isDampingHigh ? 0.8 : 0.6;
            parentBody.angularDamping = isDampingHigh ? 0.9 : 0.7;
            childBody.linearDamping = isDampingHigh ? 0.8 : 0.6;
            childBody.angularDamping = isDampingHigh ? 0.9 : 0.7;
            
            // Add to world
            world.addConstraint(constraint);
            
            // Store constraint for later
            physicsConstraintsRef.current.push({
              constraint: constraint,
              parentBody: parentBody,
              childBody: childBody,
              parentMesh: parentMesh,
              childMesh: childMesh,
              parentName: connection.parent,
              childName: childName,
              broken: false,
              isDistanceConstraint: false
            });
            
            console.log(`🔗 Created constraint between ${connection.parent} and ${childName}`);
          });
        });
        
        // Position the bandit at the center of the scene
        bandit.position.set(0, 0, 0); // Always spawn at center
        
        // Find the root mesh/group that we want to work with
        let modelRoot = bandit;
        bandit.traverse((node) => {
          if (node.isMesh) {
            node.castShadow = true;
            node.receiveShadow = true;
            node.material.shadowSide = THREE.FrontSide;
            
            // If materials need updating
            if (node.material) {
              node.material.needsUpdate = true;
            }
          }
        });
        
        scene.add(bandit);
        banditsRef.current.push(bandit);

        // Create skeleton helper
        const skeletonHelper = new SkeletonHelper(bandit);
        skeletonHelper.visible = skeletonVisibleRef.current; // Set initial visibility
        skeletonHelper.material.linewidth = 3; // Make lines thicker
        scene.add(skeletonHelper);
        skeletonHelpersRef.current.push(skeletonHelper);

        console.log(`📊 Stats: ${bones.length} bones, ${meshParts.length} meshes, ${boneToMeshMap.size} mapped bones-to-meshes`);
      }
    }, 
    // Progress callback
    (xhr) => {
      console.log(`📥 Loading: ${(xhr.loaded / xhr.total * 100).toFixed(0)}%`);
    },
    // Error callback
    (error) => {
      console.error('Error loading model:', error);
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

    // Add physics helpers
    const dragHelper = {
      // For converting mouse position to 3D position
      getMousePositionIn3D: (event, camera, targetY = null) => {
        // Create normalized device coordinates (-1 to +1)
        const mouse = new THREE.Vector2(
          (event.clientX / window.innerWidth) * 2 - 1,
          -(event.clientY / window.innerHeight) * 2 + 1
        );
        
        // Create raycaster
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, camera);
        
        if (targetY !== null) {
          // Find intersection with a horizontal plane at height targetY
          const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -targetY);
          const intersection = new THREE.Vector3();
          raycaster.ray.intersectPlane(plane, intersection);
          return intersection;
        } else {
          // Use fixed distance from camera if no plane intersection
          const pos = new THREE.Vector3();
          pos.copy(raycaster.ray.direction);
          pos.multiplyScalar(10); // 10 units from camera
          pos.add(camera.position);
          return pos;
        }
      },
      
      // Find the mesh and body at the given mouse coordinates
      findBodyAtMouse: (event, camera, meshPartsRef) => {
        // Create normalized device coordinates
        const mouse = new THREE.Vector2(
          (event.clientX / window.innerWidth) * 2 - 1,
          -(event.clientY / window.innerHeight) * 2 + 1
        );
        
        // Create and setup raycaster
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, camera);
        
        // Get all meshes
        const meshes = meshPartsRef.current.map(item => item.mesh);
        
        // Find intersections
        const intersects = raycaster.intersectObjects(meshes);
        
        if (intersects.length > 0) {
          const hitMesh = intersects[0].object;
          const meshPhysicsInfo = meshPartsRef.current.find(item => item.mesh === hitMesh);
          
          if (meshPhysicsInfo) {
            return {
              body: meshPhysicsInfo.body,
              mesh: hitMesh,
              point: intersects[0].point
            };
          }
        }
        
        return null;
      },
      
      // Create a constraint to drag a body
      createDragConstraint: (body, position, world) => {
        if (!body) return null;
        
        // Reset mass temporarily if body is frozen
        let wasFrozen = false;
        if (body.isFrozen) {
          body.mass = body.initialMass;
          body.updateMassProperties();
          body.isFrozen = false;
          wasFrozen = true;
          
          // Since we're unfreezing, apply the same unfreezing logic as in the shooting mode
          meshPartsRef.current.forEach(part => {
            if (part.body.isFrozen) {
              part.body.mass = part.body.initialMass;
              part.body.updateMassProperties();
              part.body.isFrozen = false;
              
              // Calculate distance factor for connected parts
              const hitPos = body.position;
              const partPos = part.body.position;
              const distSquared = 
                Math.pow(hitPos.x - partPos.x, 2) + 
                Math.pow(hitPos.y - partPos.y, 2) + 
                Math.pow(hitPos.z - partPos.z, 2);
              
              // Impulse diminishes with square of distance
              const distanceFactor = Math.min(1.0, 1.0 / (1.0 + distSquared));
              
              if (distanceFactor > 0.5) {
                // Only unfreeze closely connected parts
                part.body.mass = part.body.initialMass;
                part.body.updateMassProperties();
                part.body.isFrozen = false;
                
                // Apply very small random impulse to wake up the physics
                const wakeImpulse = new CANNON.Vec3(
                  (Math.random() - 0.5) * 0.1,
                  (Math.random() - 0.5) * 0.1,
                  (Math.random() - 0.5) * 0.1
                );
                part.body.applyImpulse(wakeImpulse, new CANNON.Vec3(0, 0, 0));
              }
            }
          });
        }
        
        // Create a zero mass body for the cursor
        const cursorBody = new CANNON.Body({
          mass: 0, // Static body
          position: new CANNON.Vec3(position.x, position.y, position.z)
        });
        
        // Add to world
        world.addBody(cursorBody);
        
        // Create constraint between cursor and dragged body
        const constraint = new CANNON.PointToPointConstraint(
          body,
          new CANNON.Vec3(position.x - body.position.x, position.y - body.position.y, position.z - body.position.z),
          cursorBody,
          new CANNON.Vec3(0, 0, 0),
          50 // Reduced force for softer dragging
        );
        
        // Add constraint to world
        world.addConstraint(constraint);
        
        return {
          constraint,
          cursorBody,
          wasFrozen
        };
      },
      
      // Update the position of the drag constraint
      updateDragConstraint: (constraint, position) => {
        if (constraint && constraint.cursorBody) {
          constraint.cursorBody.position.copy(position);
        }
      },
      
      // Remove the drag constraint
      removeDragConstraint: (constraint, world) => {
        if (constraint && constraint.constraint) {
          world.removeConstraint(constraint.constraint);
          world.removeBody(constraint.cursorBody);
        }
      }
    };
    
    // Store dragHelper in ref for access outside useEffect
    dragHelperRef.current = dragHelper;

    // Mouse event handlers for dragging and shooting
    const onMouseDown = (event) => {
      // Left mouse button for shooting
      if (event.button === 0) {
        onShoot(event);
      }
      // Middle mouse button for dragging
      else if (event.button === 1) {
        event.preventDefault(); // Prevent default browser behavior for middle click
        
        // Find body under mouse
        const result = dragHelper.findBodyAtMouse(event, camera, meshPartsRef);
        
        if (result) {
          // Create dragging constraint
          const dragPos = new CANNON.Vec3(
            result.point.x,
            result.point.y,
            result.point.z
          );
          
          // Create drag constraint
          dragConstraintRef.current = dragHelper.createDragConstraint(
            result.body,
            dragPos,
            world
          );
          
          draggedBodyRef.current = result.body;
          
          // Create a dragging plane that faces the camera for full 3D movement
          // Get camera direction
          const cameraDirection = new THREE.Vector3();
          camera.getWorldDirection(cameraDirection);
          
          // Create a plane perpendicular to the camera's view direction
          const planeNormal = cameraDirection;
          // Position the plane at the hit point
          const planeConstant = -planeNormal.dot(new THREE.Vector3(result.point.x, result.point.y, result.point.z));
          dragPlaneRef.current = new THREE.Plane(planeNormal, planeConstant);
        }
      }
      // Right mouse button is handled by OrbitControls
    };
    
    const onMouseMove = (event) => {
      if (dragConstraintRef.current) {
        // Get 3D position from mouse
        const intersection = new THREE.Vector3();
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2(
          (event.clientX / window.innerWidth) * 2 - 1,
          -(event.clientY / window.innerHeight) * 2 + 1
        );
        
        raycaster.setFromCamera(mouse, camera);
        
        // Find intersection with drag plane
        if (raycaster.ray.intersectPlane(dragPlaneRef.current, intersection)) {
          // Convert to CANNON vector
          const targetPos = new CANNON.Vec3(
            intersection.x,
            intersection.y,
            intersection.z
          );
          
          // Update constraint
          dragHelper.updateDragConstraint(dragConstraintRef.current, targetPos);
        }
      }
    };
    
    const onMouseUp = (event) => {
      // Handle middle mouse button release for dragging
      if (event.button === 1 && dragConstraintRef.current) {
        // Remove constraint
        dragHelper.removeDragConstraint(dragConstraintRef.current, world);
        dragConstraintRef.current = null;
        draggedBodyRef.current = null;
      }
    };

    // Function to handle shooting
    const onShoot = (event) => {
      mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      
      // Create array of all meshes to check for intersection
      const targetMeshes = [];
      banditsRef.current.forEach(bandit => {
        bandit.traverse(child => {
          if (child.isMesh || child.isSkinnedMesh) {
            targetMeshes.push(child);
          }
        });
      });
      
      // Check for direct mesh intersections (precise hit detection)
      const intersects = raycaster.intersectObjects(targetMeshes);

      if (intersects.length > 0) {
        const hitMesh = intersects[0].object;
        const intersectionPoint = intersects[0].point; // Get the exact intersection point
        
        // Calculate shooting direction vector (from camera to hit point)
        const cameraPosition = new THREE.Vector3();
        camera.getWorldPosition(cameraPosition);
        
        // This is the direction the shot came from
        const shootingDirection = new THREE.Vector3()
          .subVectors(intersectionPoint, cameraPosition)
          .normalize();
          
        // Calculate the opposite direction (for push-back effect)
        const oppositeDirection = shootingDirection.clone().negate();
        
        // Find physics body for this mesh
        const meshPhysicsInfo = meshPartsRef.current.find(item => item.mesh === hitMesh);
        
        // Find which bandit this mesh belongs to
        let banditIndex = -1;
        banditsRef.current.forEach((bandit, index) => {
          bandit.traverse(child => {
            if (child === hitMesh) {
              banditIndex = index;
            }
          });
        });
        
        if (banditIndex !== -1) {
          // Play random hit sound
          const randomHitSound = hitSounds[Math.floor(Math.random() * hitSounds.length)];
          const hitAudio = new Audio(randomHitSound);
          hitAudio.volume = volume; // Set volume
          hitAudio.play();

          // Calculate impact force based on hit location
          // Stronger hits for head and chest, medium hits for limbs
          let impactMultiplier = 1.0;
          if (hitMesh.name.includes("Head")) {
            impactMultiplier = 1.8; // Headshots have more impact
          } else if (hitMesh.name.includes("Chest") || hitMesh.name.includes("Hips")) {
            impactMultiplier = 1.5; // Torso shots have medium-high impact
          } else if (hitMesh.name.includes("Hand") || hitMesh.name.includes("Foot")) {
            impactMultiplier = 0.8; // Extremities have less impact
          }
          
          // Always allow hitting parts that are already on the ground
          // Increase impulse for parts that are resting
          if (meshPhysicsInfo) {
            // Check if part is near ground
            const isNearGround = meshPhysicsInfo.body.position.y < 0.5;
            
            // Temporarily reduce damping for hit parts on ground to allow movement
            if (isNearGround) {
              meshPhysicsInfo.body.linearDamping = 0.4; // Lower damping when hit
              meshPhysicsInfo.body.angularDamping = 0.4;
              impactMultiplier *= 1.5; // Boost impact on grounded parts
            }
            
            // Base impulse force (strength of the hit)
            const impactForce = 10 * impactMultiplier;
            
            // Apply impulse in the opposite direction from the shot
            // This creates a realistic push-back effect
            const impulse = new CANNON.Vec3(
              oppositeDirection.x * impactForce,
              oppositeDirection.y * impactForce + (isNearGround ? 0.5 : 0), // Add slight upward force for ground parts
              oppositeDirection.z * impactForce
            );
            
            // Special handling for specific body parts
            if (hitMesh.name.includes("Arm") || hitMesh.name.includes("Leg")) {
              // For limbs, keep the opposite direction but modify the impulse
              const bodyCenter = new THREE.Vector3(0, 0, 0); // Assume model center is origin
              
              // Specific handling for lower leg (knee) hits to prevent unnatural movement
              if (hitMesh.name.includes("LowerLeg")) {
                // Apply conservative forces for knees
                impulse.x *= 0.7; // Reduce sideways force
                impulse.z *= 0.7;
                
                // Add rotation directly using angular velocity for natural bending
                const bendStrength = 5 * impactMultiplier;
                meshPhysicsInfo.body.angularVelocity.set(
                  bendStrength, // X rotation for knee bend
                  meshPhysicsInfo.body.angularVelocity.y * 0.5,
                  meshPhysicsInfo.body.angularVelocity.z * 0.5
                );
                
                // Also handle upper leg for consistent movement
                const upperLegInfo = meshPartsRef.current.find(part => 
                  part.mesh.name.includes("UpperLeg") && 
                  part.body !== meshPhysicsInfo.body
                );
                
                if (upperLegInfo) {
                  // Apply matching impulse to upper leg
                  upperLegInfo.body.applyImpulse(
                    new CANNON.Vec3(impulse.x * 0.8, impulse.y * 0.8, impulse.z * 0.8),
                    new CANNON.Vec3(0, 0, 0)
                  );
                  upperLegInfo.body.angularDamping = 0.9;
                }
              }
              // Special handling for hands to improve their hit response
              else if (hitMesh.name.includes("Hand")) {
                // Hands should have more dramatic response
                impulse.x *= 1.2; // Increase lateral movement
                impulse.z *= 1.2;
                
                // Add rotational effect for natural wrist twist
                const twistStrength = 3 * impactMultiplier;
                meshPhysicsInfo.body.angularVelocity.set(
                  meshPhysicsInfo.body.angularVelocity.x * 0.7,
                  meshPhysicsInfo.body.angularVelocity.y * 0.7,
                  twistStrength // Z rotation for wrist twist
                );
                
                // Also affect the connected forearm for consistent arm movement
                const elbowInfo = meshPartsRef.current.find(part => 
                  part.mesh.name.includes("Elbow") && 
                  part.body !== meshPhysicsInfo.body
                );
                
                if (elbowInfo) {
                  // Apply smaller matching impulse to forearm
                  elbowInfo.body.applyImpulse(
                    new CANNON.Vec3(impulse.x * 0.4, impulse.y * 0.4, impulse.z * 0.4),
                    new CANNON.Vec3(0, 0, 0)
                  );
                  // Temporarily reduce damping for more responsive arm movement
                  elbowInfo.body.linearDamping = 0.5;
                }
              }
            } 
            else if (hitMesh.name.includes("Head")) {
              // Head special handling - add stronger y component
              impulse.y *= 1.2; // Stronger vertical component
            }
            else if (hitMesh.name.includes("Chest") || hitMesh.name.includes("Hips")) {
              // Torso special handling - keep impulse as is for dramatic effect
            }
            
            // Apply impulse at impact point for more realistic physics
            const worldPoint = new CANNON.Vec3(
              intersectionPoint.x - meshPhysicsInfo.body.position.x,
              intersectionPoint.y - meshPhysicsInfo.body.position.y,
              intersectionPoint.z - meshPhysicsInfo.body.position.z
            );
            
            // Unfreeze if still frozen
            if (meshPhysicsInfo.body.isFrozen) {
              // Restore mass so it falls
              meshPhysicsInfo.body.mass = meshPhysicsInfo.body.initialMass;
              meshPhysicsInfo.body.updateMassProperties();
              meshPhysicsInfo.body.isFrozen = false;
              
              // Also unfreeze all connected parts with improved cascade effect
              meshPartsRef.current.forEach(part => {
                if (part.body.isFrozen) {
                  part.body.mass = part.body.initialMass;
                  part.body.updateMassProperties();
                  part.body.isFrozen = false;
                  
                  // Calculate distance factor for connected parts
                  const hitPos = meshPhysicsInfo.body.position;
                  const partPos = part.body.position;
                  const distSquared = 
                    Math.pow(hitPos.x - partPos.x, 2) + 
                    Math.pow(hitPos.y - partPos.y, 2) + 
                    Math.pow(hitPos.z - partPos.z, 2);
                  
                  // Impulse diminishes with square of distance
                  const distanceFactor = Math.min(1.0, 1.0 / (1.0 + distSquared));
                  
                  // Calculate connected part impulse direction
                  // This should be in the same direction as the main impact
                  const connectedImpulse = new CANNON.Vec3(
                    oppositeDirection.x * impactForce * 0.7 * distanceFactor,
                    oppositeDirection.y * impactForce * 0.7 * distanceFactor,
                    oppositeDirection.z * impactForce * 0.7 * distanceFactor
                  );
                  
                  // Apply impulse to connected part
                  part.body.applyImpulse(connectedImpulse, new CANNON.Vec3(0, 0, 0));
                }
              });
              
              console.log(`🔓 Unfroze physics for ${hitMesh.name} and connected parts`);
            }
            
            // Always apply the impulse whether it was frozen or not
            meshPhysicsInfo.body.applyImpulse(impulse, worldPoint);
            
            // Trigger sympathetic movement in nearby parts
            meshPartsRef.current.forEach(part => {
              if (!part.body.isFrozen && part.body !== meshPhysicsInfo.body) {
                // Calculate distance from hit part
                const hitPos = meshPhysicsInfo.body.position;
                const partPos = part.body.position;
                const distSquared = 
                  Math.pow(hitPos.x - partPos.x, 2) + 
                  Math.pow(hitPos.y - partPos.y, 2) + 
                  Math.pow(hitPos.z - partPos.z, 2);
                
                // Only affect nearby parts
                if (distSquared < 9) { // 3 units radius
                  part.body.linearDamping = Math.min(part.body.linearDamping, 0.5);
                  part.body.angularDamping = Math.min(part.body.angularDamping, 0.5);
                  
                  // Small sympathetic impulse in the same direction
                  if (part.body.position.y < 0.5) { // If on ground
                    const sympatheticImpulse = new CANNON.Vec3(
                      oppositeDirection.x * 2, 
                      0.3, // Small upward force
                      oppositeDirection.z * 2
                    );
                    part.body.applyImpulse(sympatheticImpulse, new CANNON.Vec3(0, 0, 0));
                  }
                }
              }
            });
          }

          // Display skull icon above the bandit if it's the first hit
          if (!hitBanditsRef.current.has(banditIndex)) {
            // Get the bandit model's position
            const banditPosition = banditsRef.current[banditIndex].position;
            const skullIconSprite = createSkullIcon(banditPosition);
            scene.add(skullIconSprite);
            skullIconsRef.current.push({ sprite: skullIconSprite, banditIndex: banditIndex });
            hitBanditsRef.current.add(banditIndex);

            // Update remaining bandits count
            setRemainingBandits((prevCount) => prevCount - 1);
          }

          // Trigger particle system
          if (particleSystemRef.current) {
            console.log(`💥 Impact at [${intersectionPoint.x.toFixed(2)}, ${intersectionPoint.y.toFixed(2)}, ${intersectionPoint.z.toFixed(2)}]`);
            particleSystemRef.current.triggerParticles(intersectionPoint);
          }
          
          console.log(`🎯 Hit: ${hitMesh.name} at [${intersectionPoint.x.toFixed(2)}, ${intersectionPoint.y.toFixed(2)}, ${intersectionPoint.z.toFixed(2)}]`);
        }
      }
    };

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
      sprite.position.set(position.x, position.y + 2.4, position.z); // Position it higher (+2.4 instead of +2)
      sprite.scale.set(0.4, 0.4, 0.4); // Make it 20% smaller (0.5 * 0.8 = 0.4)
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

    // Add event to prevent default middle mouse scroll behavior
    const onContextMenu = (event) => {
      // Prevent context menu for right click
      event.preventDefault();
    };

    // Add event listeners
    window.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('contextmenu', onContextMenu);

    // Animation frame ID reference for cleanup
    let animationFrameId = null;
    let prevTime = performance.now();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Calculate time delta for smoother physics on different frame rates
      const time = performance.now();
      let deltaTime = (time - prevTime) / 1000; // Convert to seconds
      
      // Cap delta time to avoid instability on slow frames
      deltaTime = Math.min(deltaTime, 1/30); // Max 1/30 seconds (min 30fps)
      
      // Step the physics world with consistent time step
      // Multiple smaller steps for better stability
      const timeStep = 1/120; // 120Hz physics simulation
      const maxSubSteps = 4; // Allow up to 4 substeps
      world.step(timeStep, deltaTime, maxSubSteps);
      
      prevTime = time;

      // PhysX-inspired muscle tension system for all body parts
      // This simulates the joint drive systems available in PhysX
      const applyMuscleTension = () => {
        physicsConstraintsRef.current.forEach(constraintInfo => {
          if (constraintInfo.broken || constraintInfo.isDistanceConstraint || constraintInfo.isAuxiliaryConstraint) {
            return; // Skip broken or auxiliary constraints
          }
           
          const parentBody = constraintInfo.parentBody;
          const childBody = constraintInfo.childBody;
          
          if (!parentBody.isFrozen && !childBody.isFrozen) {
            // Get current rotation and angular velocity
            const childAngVel = childBody.angularVelocity;
            
            // Determine rest position and configuration based on body part
            let restDirection = new CANNON.Vec3(0, -1, 0); // Default down
            let stiffness = 0.5;
            let damping = 0.5;
            let multiplier = 5.0;
            
            // Customize behavior based on body part
            if (constraintInfo.childName.includes("Head")) {
              // Head should stay upright
              restDirection.set(0, 1, 0);
              stiffness = 0.9; // Strong neck muscles
              damping = 0.8;   // High damping for stability
              multiplier = 8.0; // Stronger correction
            } 
            else if (constraintInfo.childName.includes("Elbow") || constraintInfo.childName.includes("Hand")) {
              // Arms naturally hang down
              restDirection.set(0, -1, 0.1); // Slightly forward
              stiffness = 0.7;
              damping = 0.5;
              multiplier = 6.0;
            } 
            else if (constraintInfo.childName.includes("UpperArm")) {
              // Shoulders tend to be drawn inward & down
              restDirection.set(0, -0.7, constraintInfo.childName.includes("Left") ? 0.7 : -0.7);
              stiffness = 0.6;
              damping = 0.6;
              multiplier = 5.0;
            }
            else if (constraintInfo.childName.includes("LowerLeg")) {
              // Knees naturally straighten
              restDirection.set(0, -1, 0);
              stiffness = 0.9; // Strong knee straightening
              damping = 0.7;
              multiplier = 7.0;
            }
            else if (constraintInfo.childName.includes("UpperLeg")) {
              // Hips tend to be centered
              restDirection.set(0, -1, 0);
              stiffness = 0.8;
              damping = 0.7;
              multiplier = 6.0;
            }
            else if (constraintInfo.childName.includes("Foot")) {
              // Feet naturally flat
              restDirection.set(0, 0, 1); // Forward
              stiffness = 0.7;
              damping = 0.6;
              multiplier = 5.0;
            }
            
            // Calculate current direction
            const currentDirection = new CANNON.Vec3();
            currentDirection.copy(childBody.position);
            currentDirection.vsub(parentBody.position, currentDirection);
            currentDirection.normalize();
            
            // Calculate how far from rest we are
            const dot = currentDirection.dot(restDirection);
            const restoring = 1.0 - Math.abs(dot); // Higher when far from rest
            
            // Apply corrective torque to simulate muscle tension trying to return body to rest
            if (restoring > 0.05) { // Only when away from rest
              // Cross product to get correction axis
              const correctionAxis = new CANNON.Vec3();
              currentDirection.cross(restDirection, correctionAxis);
              
              // Ensure we have a valid correction (avoid NaN)
              if (correctionAxis.length() > 0.01) {
                correctionAxis.normalize();
                
                // Calculate restoring torque - stronger when further from rest
                const restoreTorque = new CANNON.Vec3();
                correctionAxis.scale(stiffness * restoring * multiplier, restoreTorque);
                
                // Apply damping to prevent oscillation (PhysX-like effect)
                const dampingTorque = new CANNON.Vec3();
                childAngVel.scale(-damping, dampingTorque);
                
                // Combine forces
                restoreTorque.vadd(dampingTorque, restoreTorque);
                
                // Apply the torque to create muscle tension effect
                childBody.torque.vadd(restoreTorque, childBody.torque);
              }
              
              // Adjust damping dynamically based on motion
              const speed = childAngVel.length();
              if (speed < 0.5) {
                // When nearly stopped, increase damping for stability
                childBody.angularDamping = Math.min(0.9, childBody.angularDamping + 0.05);
              } else if (speed < 2.0) {
                // Medium speed, moderate damping
                childBody.angularDamping = Math.min(0.8, childBody.angularDamping);
              } else {
                // Fast movement, reduce damping to allow natural motion
                childBody.angularDamping = Math.max(0.6, childBody.angularDamping - 0.05);
              }
            }
          }
        });
      };
      
      // Apply the PhysX-inspired muscle tension system
      applyMuscleTension();

      // Additional knee correction for CANNON.js versions without angularFactor
      meshPartsRef.current.forEach(({ mesh, body }) => {
        // Apply special knee rotation correction if needed
        if (!body.isFrozen && body.additionalKneeCorrection) {
          // Keep only X-axis rotation by zeroing out Y and Z components
          const quaternion = body.quaternion;
          
          // Extract Euler angles - this is a simplified approach
          const euler = new CANNON.Vec3();
          
          // Keep X rotation, heavily reduce Y and Z
          if (Math.abs(body.angularVelocity.y) > 0.1) {
            body.angularVelocity.y *= 0.1; // Reduce Y rotation
          }
          
          if (Math.abs(body.angularVelocity.z) > 0.1) {
            body.angularVelocity.z *= 0.1; // Reduce Z rotation
          }
        }
        
        if (!body.isFrozen) {
          // Update mesh position from physics body
          mesh.position.set(
            body.position.x,
            body.position.y,
            body.position.z
          );
          
          // Update mesh rotation from physics body
          mesh.quaternion.set(
            body.quaternion.x,
            body.quaternion.y,
            body.quaternion.z,
            body.quaternion.w
          );
          
          // Prevent excessive rolling on ground
          // If body is near the ground, apply additional damping and limit angular velocity
          if (body.position.y < 0.3) { // If close to ground
            // Check if the body is moving significantly
            const isMoving = 
              Math.abs(body.velocity.x) > 0.5 || 
              Math.abs(body.velocity.y) > 0.5 || 
              Math.abs(body.velocity.z) > 0.5 ||
              Math.abs(body.angularVelocity.x) > 0.5 ||
              Math.abs(body.angularVelocity.y) > 0.5 ||
              Math.abs(body.angularVelocity.z) > 0.5;
            
            // Apply different damping based on whether the body is moving or stationary
            if (isMoving) {
              // Moderate damping for moving parts
              body.linearDamping = 0.7;
              body.angularDamping = 0.7;
            } else {
              // Higher damping for parts at rest (but still less than before)
              body.linearDamping = 0.85; // Reduced from 0.95
              body.angularDamping = 0.85; // Reduced from 0.95
            }
            
            // Limit angular velocity to prevent excessive rolling/spinning
            const maxAngularVelocity = 3.0;
            const angVel = body.angularVelocity;
            const angVelMagnitude = Math.sqrt(
              angVel.x * angVel.x + 
              angVel.y * angVel.y + 
              angVel.z * angVel.z
            );
            
            if (angVelMagnitude > maxAngularVelocity) {
              const scale = maxAngularVelocity / angVelMagnitude;
              body.angularVelocity.x *= scale;
              body.angularVelocity.y *= scale;
              body.angularVelocity.z *= scale;
            }
            
            // Apply small upward force to prevent parts from sinking into ground
            // This reduces the appearance of clipping through ground
            body.applyLocalForce(
              new CANNON.Vec3(0, 1, 0), // Up direction
              new CANNON.Vec3(0, 0, 0)  // At center of mass
            );
          } else {
            // Reset to normal damping when not on ground
            // Use the previously set damping values from constraints
            const isDampingHigh = mesh.name.includes("Head") || mesh.name.includes("Hips");
            body.linearDamping = isDampingHigh ? 0.8 : 0.6;
            body.angularDamping = isDampingHigh ? 0.9 : 0.7;
          }
        }
      });
      
      // Check constraints for breaking with improved mechanics
      physicsConstraintsRef.current.forEach(constraintInfo => {
        if (!constraintInfo.broken) {
          // If bodies are too far apart, break the constraint
          const parentPos = constraintInfo.parentBody.position;
          const childPos = constraintInfo.childBody.position;
          
          // Calculate distance between parts
          const distance = Math.sqrt(
            Math.pow(parentPos.x - childPos.x, 2) +
            Math.pow(parentPos.y - childPos.y, 2) +
            Math.pow(parentPos.z - childPos.z, 2)
          );
          
          // Dynamic break threshold based on joint type for more realistic dismemberment
          let breakThreshold = 1.5; // Default threshold
          
          if (constraintInfo.isDistanceConstraint) {
            // Distance constraints have their own logic
            // If the main constraint is broken, break the distance constraint too
            const mainConstraint = physicsConstraintsRef.current.find(
              info => !info.isDistanceConstraint && 
                      info.parentName === constraintInfo.parentName && 
                      info.childName === constraintInfo.childName
            );
            
            if (mainConstraint && mainConstraint.broken) {
              world.removeConstraint(constraintInfo.constraint);
              constraintInfo.broken = true;
            }
            return;
          }
          
          // If a custom break threshold is set for this constraint, use it
          if (constraintInfo.customBreakThreshold) {
            breakThreshold = constraintInfo.customBreakThreshold;
          }
          // Otherwise use standard thresholds based on body part
          else if (constraintInfo.childName.includes("Hand") || constraintInfo.childName.includes("Foot")) {
            breakThreshold = 1.2; // Extremities break more easily
          } else if (constraintInfo.childName.includes("Head")) {
            breakThreshold = 1.8; // Head is harder to break off
          } else if (constraintInfo.childName.includes("Upper")) {
            breakThreshold = 1.6; // Upper limbs break with medium difficulty
          }
          
          // Calculate break probability based on distance
          // The closer to the threshold, the higher the chance to break
          // This prevents parts from stretching unnaturally before breaking
          const distanceRatio = distance / breakThreshold;
          const breakProbability = Math.pow(distanceRatio, 3); // Cubic function for sharp increase near threshold
          
          // Random chance to break earlier to prevent stretched look
          const shouldBreakEarly = distanceRatio > 0.85 && Math.random() < breakProbability;
          
          if (distance > breakThreshold || shouldBreakEarly) {
            // Remove constraint from world
            world.removeConstraint(constraintInfo.constraint);
            constraintInfo.broken = true;
            
            // Also remove any associated distance constraints
            const distConstraint = physicsConstraintsRef.current.find(
              info => info.isDistanceConstraint && 
                      info.parentName === constraintInfo.parentName && 
                      info.childName === constraintInfo.childName
            );
            
            if (distConstraint && !distConstraint.broken) {
              world.removeConstraint(distConstraint.constraint);
              distConstraint.broken = true;
            }
            
            // Also remove any auxiliary constraints
            const auxConstraints = physicsConstraintsRef.current.filter(
              info => info.isAuxiliaryConstraint && 
                      info.parentName === constraintInfo.parentName && 
                      info.childName === constraintInfo.childName
            );
            
            auxConstraints.forEach(auxInfo => {
              if (!auxInfo.broken) {
                world.removeConstraint(auxInfo.constraint);
                auxInfo.broken = true;
              }
            });
            
            console.log(`💥 Broke constraint between ${constraintInfo.parentName} and ${constraintInfo.childName}`);
            
            // Apply small explosion impulse to separated parts for dramatic effect
            const explosionForce = 5;
            const direction = new CANNON.Vec3(
              childPos.x - parentPos.x,
              childPos.y - parentPos.y,
              childPos.z - parentPos.z
            );
            
            // Normalize direction
            const length = Math.sqrt(
              direction.x * direction.x + 
              direction.y * direction.y + 
              direction.z * direction.z
            );
            
            if (length > 0) {
              direction.x /= length;
              direction.y /= length;
              direction.z /= length;
              
              // Apply impulse in separation direction
              constraintInfo.childBody.applyImpulse(
                new CANNON.Vec3(
                  direction.x * explosionForce,
                  direction.y * explosionForce,
                  direction.z * explosionForce
                ),
                new CANNON.Vec3(0, 0, 0)
              );
            }
          }
        }
      });

      // No need to update hitbox visibility as we're no longer using them

      // Update skeleton helper visibility
      skeletonHelpersRef.current.forEach((helper) => {
        if (helper) {
          helper.visible = skeletonVisibleRef.current;
        }
      });

      // Update skull icon positions
      skullIconsRef.current.forEach(({ sprite, banditIndex }) => {
        const banditPosition = banditsRef.current[banditIndex].position;
        sprite.position.set(banditPosition.x, banditPosition.y + 2.4, banditPosition.z); // Update to match createSkullIcon (+2.4)
      });

      // Prevent camera from going underground
      if (camera.position.y < 1) {
        camera.position.y = 1;
      }

      controls.update(); // Update controls
      renderer.render(scene, camera);
    };

    animate();

    // Add debugging in the useEffect
    console.log('🔧 Initial state:', {
      skeleton: skeletonVisibleRef.current ? 'visible' : 'hidden'
    });

    console.log('💀 Skeleton:', skeletonVisibleRef.current ? 'VISIBLE' : 'HIDDEN');

    return () => {
      // Cancel animation frame
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }

      // Remove all event listeners
      window.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('contextmenu', onContextMenu);
      
      // Remove constraints from world
      physicsConstraintsRef.current.forEach(constraintInfo => {
        if (!constraintInfo.broken) {
          world.removeConstraint(constraintInfo.constraint);
        }
      });
      
      // Remove physics bodies from world
      meshPhysicsBodiesRef.current.forEach(body => {
        world.removeBody(body);
      });
      
      // Dispose of THREE.js objects
      scene.traverse((object) => {
        if (object.geometry) {
          object.geometry.dispose();
        }
        
        if (object.material) {
          if (Array.isArray(object.material)) {
            object.material.forEach(material => material.dispose());
          } else {
            object.material.dispose();
          }
        }
      });
      
      // Clear all objects from the scene
      while(scene.children.length > 0) {
        scene.remove(scene.children[0]);
      }
      
      // Clear references
      banditsRef.current = [];
      hitboxesRef.current = [];
      skullIconsRef.current = [];
      hitBanditsRef.current.clear();
      skeletonHelpersRef.current = [];
      meshPhysicsBodiesRef.current = [];
      meshPartsRef.current = [];
      physicsConstraintsRef.current = [];
      bonePhysicsBodiesRef.current = [];
      
      // Dispose of renderer
      renderer.dispose();
      
      // Remove renderer DOM element
      if (mountRef.current && mountRef.current.contains(renderer.domElement)) {
        mountRef.current.removeChild(renderer.domElement);
      }
      
      // Dispose of controls
      controls.dispose();
    };
  }, [volume]); // Remove interactionMode dependency

  const handleLeaveArea = () => {
    history.push('/looting');
  };

  const toggleSkeleton = () => {
    // Toggle the visibility reference directly
    skeletonVisibleRef.current = !skeletonVisibleRef.current;
    
    // Update React state for UI button text
    setShowSkeleton(skeletonVisibleRef.current);
    
    // Update all skeleton helpers immediately
    skeletonHelpersRef.current.forEach(helper => {
      if (helper) {
        helper.visible = skeletonVisibleRef.current;
      }
    });
    
    console.log('🔧 Skeleton:', skeletonVisibleRef.current ? 'VISIBLE' : 'HIDDEN');
  };

  const toggleDebugMenu = () => {
    setShowDebugMenu(prevState => !prevState);
  };

  return (
    <div ref={mountRef} className="wasteland-container">
      <ParticleSystem ref={particleSystemRef} scene={sceneRef.current} />
      
      {/* Debug Button */}
      <button 
        onClick={toggleDebugMenu}
        style={{
          position: 'absolute',
          top: '20px',
          right: '20px',
          zIndex: 1000,
          backgroundColor: '#000000',
          color: '#ffffff',
          border: '2px solid #ffffff',
          borderRadius: '4px',
          padding: '10px 20px',
          margin: '0',
          boxShadow: '0 4px #ffffff',
          fontFamily: 'Almendra, serif',
          fontSize: '16px',
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}
      >
        {showDebugMenu ? 'HIDE DEBUG' : 'DEBUG'}
      </button>
      
      {/* Retractable Debug Menu */}
      {showDebugMenu && (
        <div style={{
          position: 'absolute',
          top: '80px',
          right: '20px',
          zIndex: 1000,
          backgroundColor: '#000000',
          border: '1px solid #ffffff',
          borderRadius: '8px',
          padding: '15px',
          boxShadow: '0 0 10px rgba(255, 255, 255, 0.1)',
          fontFamily: 'Almendra, serif',
          color: '#ffffff',
          width: '200px'
        }}>
          <h2 style={{ margin: '0 0 15px 0', textAlign: 'center', fontSize: '18px' }}>Debug Options</h2>
          
          <button 
            onClick={toggleSkeleton}
            style={{
              width: '100%',
              padding: '10px',
              margin: '5px 0',
              backgroundColor: '#000000',
              color: '#ffffff',
              border: '2px solid #ffffff',
              borderRadius: '4px',
              fontFamily: 'Almendra, serif',
              fontSize: '14px',
              cursor: 'pointer',
              boxShadow: '0 4px #ffffff',
              transition: 'all 0.2s ease'
            }}
          >
            {showSkeleton ? 'Hide Skeleton' : 'Show Skeleton'}
          </button>
          
          {/* You can add more debug options here */}
        </div>
      )}
      
      {remainingBandits === 0 && (
        <button onClick={handleLeaveArea} className="leave-area-button">
          Leave area
        </button>
      )}
    </div>
  );
};

export default Wasteland;