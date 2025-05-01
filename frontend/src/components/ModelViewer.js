import React, { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';

/**
 * Comprehensive ModelViewer component that handles API communication and 3D rendering
 */
const ModelViewer = () => {
  // API and routing state
  const [modelData, setModelData] = useState(null);
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState(null);
  const location = useLocation();

  // Three.js and rendering state
  const containerRef = useRef(null);
  const [modelLoading, setModelLoading] = useState(true);
  const [modelError, setModelError] = useState(null);
  const [debugInfo, setDebugInfo] = useState('');
  const [showDebug, setShowDebug] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  
  // Mobile optimization state
  const [isMobile, setIsMobile] = useState(false);
  const [devicePerformance, setDevicePerformance] = useState('high'); // 'low', 'medium', 'high'
  
  // State to track model loading
  const [loadingProgress, setLoadingProgress] = useState(0);
  
  // State to track the detected file extension
  const [detectedExtension, setDetectedExtension] = useState(null);

  // Three.js objects
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const modelRef = useRef(null);
  const animationIdRef = useRef(null);

  // Detect Telegram environment
  const isTelegramMode = location.pathname.includes('miniapp') || 
                         (typeof window !== 'undefined' && window.Telegram?.WebApp);

  // Detect mobile device and performance capabilities
  useEffect(() => {
    // Detect if device is mobile
    const checkMobile = () => {
      const userAgent = navigator.userAgent || navigator.vendor || window.opera;
      const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i;
      const isMobileDevice = mobileRegex.test(userAgent);
      setIsMobile(isMobileDevice);
      addDebugInfo(`Device detected as: ${isMobileDevice ? 'Mobile' : 'Desktop'}`);
      
      // Detect device performance level
      let performanceLevel = 'high';
      
      // Use hardware concurrency (CPU cores) as a performance indicator
      const cpuCores = navigator.hardwareConcurrency || 4;
      
      // Check if it's a low-end device
      if (
        isMobileDevice && 
        (
          // Low CPU cores
          cpuCores <= 4 ||
          // Check for low memory (not always available)
          (navigator.deviceMemory !== undefined && navigator.deviceMemory <= 4) ||
          // Older iPhones and Android devices
          /iPhone\s(5|6|7|8|SE)|Android.*\s(4|5|6)\./.test(userAgent)
        )
      ) {
        performanceLevel = 'low';
      } 
      // Medium performance
      else if (isMobileDevice) {
        performanceLevel = 'medium';
      }
      
      setDevicePerformance(performanceLevel);
      addDebugInfo(`Performance level detected: ${performanceLevel}`);
    };
    
    checkMobile();
    
    // Handle orientation change for mobile
    const handleOrientationChange = () => {
      if (rendererRef.current && containerRef.current) {
        setTimeout(() => {
          const width = containerRef.current.clientWidth;
          const height = containerRef.current.clientHeight;
          
          if (cameraRef.current) {
            cameraRef.current.aspect = width / height;
            cameraRef.current.updateProjectionMatrix();
          }
          
          if (rendererRef.current) {
            rendererRef.current.setSize(width, height);
          }
          
          addDebugInfo(`Orientation changed: ${width}x${height}`);
        }, 300); // Small delay to ensure new dimensions are available
      }
    };
    
    window.addEventListener('orientationchange', handleOrientationChange);
    
    return () => {
      window.removeEventListener('orientationchange', handleOrientationChange);
    };
  }, []);

  // Add Oswald font
  useEffect(() => {
    // Create a link element for Google Fonts
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Oswald:wght@300;400;500;600;700&display=swap';
    document.head.appendChild(link);
    
    // Set Oswald as the font for the whole app
    const style = document.createElement('style');
    style.textContent = `
      .model-viewer-container, .model-viewer-container * {
        font-family: 'Oswald', sans-serif !important;
      }
    `;
    document.head.appendChild(style);
    
    // Clean up on unmount
    return () => {
      document.head.removeChild(link);
      document.head.removeChild(style);
    };
  }, []);

  // Step 1: Fetch model data from the API or use direct params
  useEffect(() => {
    const fetchModelData = async () => {
      try {
        addDebugInfo(`App initialized`);
        
        // Get parameters from URL
        const params = new URLSearchParams(location.search);
        const modelParam = params.get('model');
        const uuidParam = params.get('uuid');
        const extParam = params.get('ext') || '.glb'; // Default to .glb if not specified
        
        // Initialize Telegram WebApp if available
        let telegramStartParam = null;
        
        if (isTelegramMode && window.Telegram?.WebApp) {
          const webApp = window.Telegram.WebApp;
          webApp.ready();
          webApp.expand();
          
          // Extract parameters from Telegram
          telegramStartParam = webApp.initDataUnsafe?.start_param;
          addDebugInfo(`Telegram WebApp detected! Start param: ${telegramStartParam || 'none'}`);
        }
        
        // Use direct model parameter if available (highest priority)
        if (modelParam) {
          addDebugInfo(`Using direct model URL from parameter: ${modelParam}`);
          setModelData({
            model_url: modelParam,
            file_extension: extParam,
            uuid: uuidParam || 'direct-load',
            base_url: window.location.origin,
            status: 'success'
          });
          setApiLoading(false);
          return;
        }
        
        // Use Telegram start_param as UUID if available (second priority)
        if (telegramStartParam && telegramStartParam.includes('-')) {
          // Determine API endpoint based on path
          let apiEndpoint = '/miniapp';
          if (location.pathname.includes('view')) {
            apiEndpoint = '/view';
          }
          
          // Add UUID parameter
          apiEndpoint += `?uuid=${telegramStartParam}`;
          if (extParam !== '.glb') {
            apiEndpoint += `&ext=${extParam}`;
          }
          
          addDebugInfo(`Fetching model data with Telegram UUID: ${telegramStartParam}`);
          addDebugInfo(`API endpoint: ${apiEndpoint}`);
          
          // Fetch from API with the UUID
          const response = await fetch(apiEndpoint);
          if (!response.ok) {
            throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
          }
          
          const data = await response.json();
          setModelData(data);
          addDebugInfo(`Model data received from API: ${JSON.stringify(data)}`);
          setApiLoading(false);
          return;
        }
        
        // Use UUID parameter directly with API (third priority)
        if (uuidParam) {
          // Determine API endpoint based on path
          let apiEndpoint = '/viewer';
          if (location.pathname.includes('miniapp')) {
            apiEndpoint = '/miniapp';
          } else if (location.pathname.includes('view')) {
            apiEndpoint = '/view';
          }
          
          // Add parameters
          apiEndpoint += `?uuid=${uuidParam}`;
          if (extParam !== '.glb') {
            apiEndpoint += `&ext=${extParam}`;
          }
          
          addDebugInfo(`Fetching model data with UUID parameter: ${uuidParam}`);
          addDebugInfo(`API endpoint: ${apiEndpoint}`);
          
          // Fetch from API
          const response = await fetch(apiEndpoint);
          if (!response.ok) {
            throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
          }
          
          const data = await response.json();
          setModelData(data);
          addDebugInfo(`Model data received from API: ${JSON.stringify(data)}`);
          setApiLoading(false);
          return;
        }
        
        // No parameters available, try default API endpoint (lowest priority)
        let apiEndpoint = '/viewer';
        if (location.pathname.includes('miniapp')) {
          apiEndpoint = '/miniapp';
        } else if (location.pathname.includes('view')) {
          apiEndpoint = '/view';
        }
        
        addDebugInfo(`No parameters found, trying default endpoint: ${apiEndpoint}`);
        
        // Fetch from default API endpoint
        const response = await fetch(apiEndpoint);
        if (!response.ok) {
          throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        setModelData(data);
        addDebugInfo(`Model data received from default API: ${JSON.stringify(data)}`);
      } catch (err) {
        console.error('Error fetching model data:', err);
        setApiError(err.message);
        addDebugInfo(`API Error: ${err.message}`);
        
        // If on Telegram without model data, show specific error
        if (isTelegramMode) {
          setApiError(`Could not load model from Telegram. Please try uploading the file again.`);
        }
      } finally {
        setApiLoading(false);
      }
    };

    fetchModelData();
  }, [location, isTelegramMode]);

  // Step 2: Initialize and render the 3D model
  useEffect(() => {
    if (!modelData || apiLoading || apiError) return;

    const { model_url, file_extension, base_url, uuid } = modelData;
    let modelUrl = model_url;
    const baseUrl = base_url || window.location.origin;

    if (!modelUrl) {
      setModelError('No model URL provided. Please provide a valid 3D model URL.');
      setModelLoading(false);
      return;
    }

    // Log the final model URL we're using
    addDebugInfo(`Final model URL to load: ${modelUrl}`);

    // Initialize Three.js scene
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);
    
    // Add a grid to help with spatial orientation
    const gridSize = 20;
    const gridDivisions = 20;
    const gridHelper = new THREE.GridHelper(gridSize, gridDivisions, 0x888888, 0xcccccc);
    scene.add(gridHelper);
    
    sceneRef.current = scene;

    // Camera with wider field of view for better visibility
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000);
    camera.position.set(10, 8, 10); // Start with a better viewing angle
    cameraRef.current = camera;

    // Renderer with mobile optimizations
    const renderer = new THREE.WebGLRenderer({ 
      antialias: !isMobile || devicePerformance === 'high',  // Disable antialiasing on low/medium mobile
      powerPreference: 'high-performance',
      alpha: false,
      stencil: false
    });
    
    // Set pixel ratio based on device performance
    if (isMobile) {
      switch (devicePerformance) {
        case 'low':
          renderer.setPixelRatio(Math.min(1.0, window.devicePixelRatio));
          break;
        case 'medium':
          renderer.setPixelRatio(Math.min(1.5, window.devicePixelRatio));
          break;
        default:
          renderer.setPixelRatio(Math.min(2.0, window.devicePixelRatio));
      }
      addDebugInfo(`Mobile renderer: Pixel ratio set to ${renderer.getPixelRatio()}`);
    } else {
    renderer.setPixelRatio(window.devicePixelRatio);
    }
    
    renderer.setSize(width, height);
    
    // Configure shadows based on device performance
    if (devicePerformance === 'low') {
      renderer.shadowMap.enabled = false;
      addDebugInfo('Shadows disabled for performance');
    } else {
    renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = devicePerformance === 'high' 
        ? THREE.PCFSoftShadowMap  // Better quality shadows for high-end devices
        : THREE.BasicShadowMap;    // Basic shadows for medium devices
      addDebugInfo(`Shadow quality set to: ${devicePerformance === 'high' ? 'high' : 'medium'}`);
    }
    
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting optimized for mobile
    // Ambient light for general illumination
    const ambientLight = new THREE.AmbientLight(0xffffff, isMobile ? 0.6 : 0.5);
    scene.add(ambientLight);

    // Only add complex lighting on medium/high performance devices
    if (devicePerformance !== 'low') {
    // Directional light with shadows
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
      
      if (devicePerformance === 'high') {
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 1024;
    directionalLight.shadow.mapSize.height = 1024;
      } else if (devicePerformance === 'medium') {
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 512;
        directionalLight.shadow.mapSize.height = 512;
      }
      
    scene.add(directionalLight);
    
      // Hemisphere light for more natural lighting (only on high-end devices)
      if (devicePerformance === 'high') {
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);
      }
    } else {
      // For low-end devices, just add a simple directional light without shadows
      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
      directionalLight.position.set(5, 10, 7);
      scene.add(directionalLight);
    }

    // Controls optimized for mobile
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = !isMobile || devicePerformance !== 'low';  // Disable damping on low-end mobile
    controls.dampingFactor = isMobile ? 0.2 : 0.1;  // Faster damping on mobile
    controls.enableZoom = true;
    controls.enablePan = !isMobile;  // Disable panning on mobile for simpler interaction
    controls.rotateSpeed = isMobile ? 0.6 : 1.0;  // Slower rotation on mobile for more control
    controls.zoomSpeed = isMobile ? 0.8 : 1.0;  // Slower zoom on mobile
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.5;
    controls.target.set(0, 0, 0);
    controls.update();
    controlsRef.current = controls;

    // Handle window resize
    const handleResize = () => {
      if (!containerRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      
      if (cameraRef.current) {
        cameraRef.current.aspect = width / height;
        cameraRef.current.updateProjectionMatrix();
      }
      
      if (rendererRef.current) {
        rendererRef.current.setSize(width, height);
      }
    };

    window.addEventListener('resize', handleResize);

    // Load the 3D model based on file extension
    // Improve file extension detection
    let extension = 'glb'; // Default to GLB/GLTF
    
    // Check various sources for the file extension in order of priority
    if (file_extension) {
      // Get from API response if available
      extension = file_extension.toLowerCase().replace('.', '');
      setDetectedExtension(extension);
      addDebugInfo(`Using file extension from API response: ${extension}`);
    } else if (modelUrl) {
      // Try to extract from URL
      const urlExtension = modelUrl.split('.').pop().toLowerCase();
      if (urlExtension && ['glb', 'gltf', 'fbx', 'obj'].includes(urlExtension)) {
        extension = urlExtension;
        setDetectedExtension(extension);
        addDebugInfo(`Extracted file extension from URL: ${extension}`);
      } else {
        // Check URL for extension indicators
        if (modelUrl.includes('.obj') || modelUrl.toLowerCase().includes('obj')) {
          extension = 'obj';
          setDetectedExtension('obj');
          addDebugInfo(`Detected OBJ model from URL pattern`);
        } else if (modelUrl.includes('.fbx') || modelUrl.toLowerCase().includes('fbx')) {
          extension = 'fbx';
          setDetectedExtension('fbx');
          addDebugInfo(`Detected FBX model from URL pattern`);
        } else if (modelUrl.includes('.gltf') || modelUrl.toLowerCase().includes('gltf')) {
          extension = 'gltf';
          setDetectedExtension('gltf');
          addDebugInfo(`Detected GLTF model from URL pattern`);
        } else if (modelUrl.includes('.glb') || modelUrl.toLowerCase().includes('glb')) {
          extension = 'glb';
          setDetectedExtension('glb');
          addDebugInfo(`Detected GLB model from URL pattern`);
        }
      }
    }
    
    addDebugInfo(`Loading model: ${modelUrl}`);
    addDebugInfo(`Using file extension: ${extension}`);

    // Added: Check the beginning of the file content for OBJ signature
    // This helps when the file extension is missing or incorrect
    const checkFileContentSignature = async () => {
      try {
        const response = await fetch(modelUrl, { method: 'HEAD' });
        if (!response.ok) return;
        
        const contentType = response.headers.get('content-type');
        // If content type indicates text or binary and we didn't already detect the right format
        if (contentType) {
          const textResponse = await fetch(modelUrl);
          if (!textResponse.ok) return;
          
          // Read the first chunk of the file to check for file signatures
          const reader = textResponse.body.getReader();
          const { value } = await reader.read();
          const text = new TextDecoder().decode(value);
          
          // Check for OBJ file signature (usually starts with # or v)
          if ((text.trim().startsWith('#') || text.trim().startsWith('v ')) && extension !== 'obj') {
            extension = 'obj';
            setDetectedExtension('obj');
            addDebugInfo(`Detected OBJ model from file content signature`);
          }
          
          // Check for FBX file signature (starts with "Kaydara FBX")
          if (text.includes('Kaydara FB') && extension !== 'fbx') {
            extension = 'fbx';
            setDetectedExtension('fbx');
            addDebugInfo(`Detected FBX model from file content signature`);
          }
        }
      } catch (error) {
        addDebugInfo(`Error checking file signature: ${error.message}`);
      }
    };
    
    // Try to check file content if the URL is accessible
    if (modelUrl && modelUrl.startsWith('http')) {
      checkFileContentSignature();
    }

    let loader;
    switch (extension) {
      case 'fbx':
        loader = new FBXLoader();
        // Set the texture path to the same directory as the model
        const modelDir = modelUrl.substring(0, modelUrl.lastIndexOf('/') + 1);
        loader.setResourcePath(modelDir);
        addDebugInfo('Using FBXLoader for FBX file');
        addDebugInfo(`Setting texture path to: ${modelDir}`);
        break;
      case 'obj':
        loader = new OBJLoader();
        addDebugInfo('Using OBJLoader for OBJ file');
        break;
      case 'glb':
      case 'gltf':
        loader = new GLTFLoader();
        addDebugInfo('Using GLTFLoader for GLTF/GLB file');
        break;
      default:
        // Try to determine from the URL as a fallback
        if (modelUrl && modelUrl.endsWith('.fbx')) {
          loader = new FBXLoader();
          addDebugInfo('Fallback: Using FBXLoader based on URL ending');
        } else if (modelUrl && modelUrl.endsWith('.obj')) {
          loader = new OBJLoader();
          addDebugInfo('Fallback: Using OBJLoader based on URL ending');
        } else {
          loader = new GLTFLoader();
          addDebugInfo('Fallback: Using default GLTFLoader');
        }
        break;
    }
    
    const onProgress = (xhr) => {
      if (xhr.lengthComputable) {
        const percentComplete = (xhr.loaded / xhr.total) * 100;
        setLoadingProgress(Math.round(percentComplete));
        addDebugInfo(`Loading: ${Math.round(percentComplete)}%`);
      }
    };

    // Standardized model processing function to ensure consistent behavior across different loaders
    const processLoadedModel = (object) => {
          setModelLoading(false);
          addDebugInfo('Model loaded successfully');

          // Handle different loader results
          let model;
          if (object.scene) {
            // GLTF/GLB result
            model = object.scene;
          } else {
            // FBX/OBJ result
            model = object;
          }
          
          // Store the model for later access
          modelRef.current = model;

      // Optimize model for mobile if needed
      if (isMobile) {
        addDebugInfo('Applying mobile optimizations to model');
        
        // For low performance devices, simplify materials
        if (devicePerformance === 'low') {
          model.traverse((child) => {
            if (child.isMesh) {
              // Skip shadows on low-end devices
              child.castShadow = false;
              child.receiveShadow = false;
              
              // Simplify materials on low-end devices
              if (child.material) {
                // Ensure materials are properly configured
                if (Array.isArray(child.material)) {
                  child.material.forEach(material => {
                    simplifyMaterial(material);
                  });
                } else {
                  simplifyMaterial(child.material);
                }
              }
            }
          });
        } else {
          // Medium to high performance - standard material optimization
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = devicePerformance === 'high';
              child.receiveShadow = devicePerformance === 'high';
              
              // Ensure materials are properly configured
              if (child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach(material => {
                    material.side = THREE.DoubleSide;
                    // Optimize textures for mobile
                    optimizeTextures(material);
                  });
                } else {
                  child.material.side = THREE.DoubleSide;
                  // Optimize textures for mobile
                  optimizeTextures(child.material);
                }
              }
            }
          });
        }
      } else {
        // Desktop - full quality
          model.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              
              // Ensure materials are properly configured
              if (child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach(material => {
                    material.side = THREE.DoubleSide;
                  });
                } else {
                  child.material.side = THREE.DoubleSide;
                }
              }
            }
          });
      }

      // Detect if this is an FBX model
      const isFbx = object.constructor.name === 'Group' && 
                    detectedExtension === 'fbx';
      
      // Special handling for FBX models
      if (isFbx) {
        addDebugInfo('Applying special normalization for FBX model');
        
        // Reset model rotation (FBX often comes with different default orientation)
        model.rotation.set(0, 0, 0);
        
        // Reset model position
        model.position.set(0, 0, 0);
      }

      // Center model and normalize size
      const box = new THREE.Box3().setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());

      addDebugInfo(`Raw model dimensions: ${size.x.toFixed(2)} x ${size.y.toFixed(2)} x ${size.z.toFixed(2)}`);
      addDebugInfo(`Center position: ${center.x.toFixed(2)}, ${center.y.toFixed(2)}, ${center.z.toFixed(2)}`);

      // Reset model position to center it at origin
      model.position.set(-center.x, -center.y, -center.z);
      model.rotation.set(0, 0, 0);

      // Standard scale calculation for consistent size
      const maxDim = Math.max(size.x, size.y, size.z);
      let scale = 5 / maxDim; // Normalize to a standard size
      
      // Apply different scaling for different model types
      if (isFbx) {
        // FBX models often need different scaling
        if (maxDim > 100) {
          scale = 5 / maxDim;
        } else if (maxDim < 1) {
          scale = 5;
        } else {
          scale = 5 / maxDim;
        }
        model.scale.set(scale, scale, scale);
        addDebugInfo(`Applied FBX scaling: ${scale.toFixed(4)}`);
      } else if (maxDim > 10 || maxDim < 0.1) {
        // For GLB and OBJ, only scale if too large or too small
        model.scale.set(scale, scale, scale);
        addDebugInfo(`Applied general scaling: ${scale.toFixed(4)}`);
      }
      
      // After scaling, recalculate the bounding box
      const scaledBox = new THREE.Box3().setFromObject(model);
      const scaledSize = scaledBox.getSize(new THREE.Vector3());
      addDebugInfo(`Scaled model dimensions: ${scaledSize.x.toFixed(2)} x ${scaledSize.y.toFixed(2)} x ${scaledSize.z.toFixed(2)}`);

      // Improved camera positioning based on model size
      const fov = camera.fov * (Math.PI / 180);
      const maxScaledDim = Math.max(scaledSize.x, scaledSize.y, scaledSize.z);
      
      // Calculate distance needed to fit the model in view
      // Adding padding factor to ensure the entire model is visible
      const padding = 1.5; // Increased padding for better visibility
      const cameraDistance = (maxScaledDim / 2) / Math.tan(fov / 2) * padding;
          
      // Set camera to a position that ensures model visibility
      const cameraZ = Math.max(cameraDistance, 5); // Minimum distance of 5 units
      
      // Position camera at an angle to better view the model
      camera.position.set(cameraZ, cameraZ * 0.8, cameraZ);
      camera.lookAt(new THREE.Vector3(0, 0, 0));
      addDebugInfo(`Camera position set to: ${cameraZ.toFixed(2)}, ${(cameraZ * 0.8).toFixed(2)}, ${cameraZ.toFixed(2)}`);
          
      // Set control target to center of model
      controls.target.set(0, 0, 0);
      controls.update();
          
      addDebugInfo(`Model dimensions: ${size.x.toFixed(2)} x ${size.y.toFixed(2)} x ${size.z.toFixed(2)}`);
          
      scene.add(model);
          
      // Stop auto-rotate after 5 seconds
      setTimeout(() => {
        if (controlsRef.current) {
          controlsRef.current.autoRotate = false;
        }
      }, 5000);
          
      // We're removing the Telegram MainButton that showed "Model Loaded"
    };
    
    // Helper function to simplify materials for low-end devices
    const simplifyMaterial = (material) => {
      // Set material to single sided for performance
      material.side = THREE.FrontSide;
      
      // Disable expensive material features
      if (material.map) {
        // Keep the diffuse map but make sure it's optimized
        optimizeTextures(material);
      } else {
        // For materials without textures, use basic material
        const color = material.color ? material.color.clone() : new THREE.Color(0xcccccc);
        material.dispose();
        
        // Replace with basic material for better performance
        const newMaterial = new THREE.MeshBasicMaterial({
          color: color,
          side: THREE.FrontSide
        });
        
        // Copy the original material's properties that we want to keep
        Object.assign(material, newMaterial);
      }
    };
    
    // Helper function to optimize textures
    const optimizeTextures = (material) => {
      // Optimize texture settings for mobile
      if (material.map) {
        material.map.generateMipmaps = devicePerformance !== 'low';
        material.map.anisotropy = devicePerformance === 'high' ? 4 : 1;
      }
      
      // Remove unnecessary textures on low-end devices
      if (devicePerformance === 'low') {
        // Keep only the essential textures
        if (material.bumpMap) {
          material.bumpMap.dispose();
          material.bumpMap = null;
        }
        if (material.normalMap) {
          material.normalMap.dispose();
          material.normalMap = null;
        }
        if (material.specularMap) {
          material.specularMap.dispose();
          material.specularMap = null;
        }
        if (material.envMap) {
          material.envMap.dispose();
          material.envMap = null;
          }
      }
    };

    // Load the model
    try {
      loader.load(
        modelUrl,
        // On load success
        (object) => processLoadedModel(object),
        // On progress
        onProgress,
        // On error
        (error) => {
          console.error('Error loading model:', error);
          
          // Check if this is a JSON parse error, which indicates wrong loader
          const isJsonError = error.message && (
            error.message.includes('Unexpected token') || 
            error.message.includes('JSON')
          );
          
          // Check specifically for OBJ files with # character
          const isLikelyObjFile = error.message && (
            (error.message.includes('Unexpected token') && error.message.includes('#')) ||
            (error.message.includes('3ds Max') || error.message.includes('#'))
          );
          
          // Check specifically for FBX files with Kaydara signature
          const isLikelyFbxFile = error.message && (
            (error.message.includes('Unexpected token') && error.message.includes('Kaydara FB')) ||
            error.message.includes('Kaydara FBX')
          );
          
          if (isLikelyFbxFile) {
            // This is very likely an FBX file - try FBXLoader directly
            addDebugInfo('Detected FBX file format from error message (Kaydara). Trying FBXLoader...');
            setDetectedExtension('fbx');
            const fbxLoader = new FBXLoader();
            // Set texture path for FBX loader in fallback
            const modelDir = modelUrl.substring(0, modelUrl.lastIndexOf('/') + 1);
            fbxLoader.setResourcePath(modelDir);
            addDebugInfo(`Setting texture path to: ${modelDir}`);
            fbxLoader.load(
              modelUrl,
              (object) => processLoadedModel(object),
              onProgress,
              (fbxError) => {
                setModelError(`Failed to load 3D model: ${fbxError.message}`);
                setModelLoading(false);
                addDebugInfo(`Error with FBXLoader: ${fbxError.message}`);
              }
            );
          } else if (isLikelyObjFile) {
            // This is very likely an OBJ file - try OBJ loader directly
            addDebugInfo('Detected OBJ file format from error message (# character). Trying OBJLoader...');
            setDetectedExtension('obj');
            const objLoader = new OBJLoader();
            objLoader.load(
              modelUrl,
              (object) => processLoadedModel(object),
              onProgress,
              (objError) => {
                setModelError(`Failed to load 3D model: ${objError.message}`);
                setModelLoading(false);
                addDebugInfo(`Error with OBJLoader: ${objError.message}`);
              }
            );
          } else if (isJsonError && extension === 'glb' && modelUrl.includes('.fbx')) {
            // Try FBX loader as fallback
            addDebugInfo('JSON parse error detected. Trying FBXLoader as fallback...');
            setDetectedExtension('fbx');
            const fbxLoader = new FBXLoader();
            // Set texture path for FBX loader in fallback
            const modelDir = modelUrl.substring(0, modelUrl.lastIndexOf('/') + 1);
            fbxLoader.setResourcePath(modelDir);
            addDebugInfo(`Setting texture path to: ${modelDir}`);
            fbxLoader.load(
              modelUrl,
              (object) => processLoadedModel(object),
              onProgress,
              (fbxError) => {
                // If FBX loader also fails, try OBJ loader
                if (modelUrl.includes('.obj') || modelUrl.toLowerCase().includes('obj')) {
                  addDebugInfo('FBXLoader failed. Trying OBJLoader as last resort...');
                  const objLoader = new OBJLoader();
                  objLoader.load(
                    modelUrl,
                    (object) => processLoadedModel(object),
                    onProgress,
                    (objError) => {
                      // Give up if all loaders fail
                      setModelError(`Failed to load 3D model: ${error.message}. Tried all available loaders.`);
                      setModelLoading(false);
                      addDebugInfo(`All loaders failed: ${objError.message}`);
                    }
                  );
                } else {
                  setModelError(`Failed to load 3D model: ${fbxError.message}`);
                  setModelLoading(false);
                  addDebugInfo(`Error with FBXLoader fallback: ${fbxError.message}`);
                }
              }
            );
          } else if (isJsonError && extension === 'glb' && (modelUrl.includes('.obj') || modelUrl.toLowerCase().includes('obj'))) {
            // Try OBJ loader as fallback
            addDebugInfo('JSON parse error detected. Trying OBJLoader as fallback...');
            setDetectedExtension('obj');
            const objLoader = new OBJLoader();
            objLoader.load(
              modelUrl,
              (object) => processLoadedModel(object),
              onProgress,
              (objError) => {
                setModelError(`Failed to load 3D model: ${objError.message}`);
                setModelLoading(false);
                addDebugInfo(`Error with OBJLoader fallback: ${objError.message}`);
              }
            );
          } else {
            // Standard error with no fallback attempted
            setModelError(`Failed to load 3D model: ${error.message}`);
            setModelLoading(false);
            addDebugInfo(`Suggestions: 
            - Check if the model URL is accessible
            - Ensure the model format matches the extension
            - Try a different model format (GLB, GLTF, FBX, OBJ)
            - Check CORS settings if loading from a different domain`);
          }
        }
      );
    } catch (err) {
      console.error('Exception during model loading:', err);
      setModelError(`Exception during model loading: ${err.message}`);
      setModelLoading(false);
    }

    // Animation loop optimized for mobile
    const animate = () => {
      // Skip frames on low-end mobile devices to improve performance
      if (isMobile && devicePerformance === 'low') {
        // Only update every other frame on low-end devices
        if (animationIdRef.current % 2 !== 0) {
          animationIdRef.current = requestAnimationFrame(animate);
          return animationIdRef.current;
        }
      }
      
      const animationId = requestAnimationFrame(animate);
      animationIdRef.current = animationId;
      
      if (controlsRef.current) {
        controlsRef.current.update();
      }
      
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
      
      return animationId;
    };
    
    animate();

    // Cleanup function - Improved unmounting with mobile optimizations
    return () => {
      window.removeEventListener('resize', handleResize);
      
      // Cancel animation frame
      if (animationIdRef.current) {
        cancelAnimationFrame(animationIdRef.current);
        animationIdRef.current = null;
      }
      
      // Dispose of Three.js resources
      if (sceneRef.current) {
        // Remove all objects from the scene first
        while (sceneRef.current.children.length > 0) {
          const object = sceneRef.current.children[0];
          sceneRef.current.remove(object);
        }
        
        sceneRef.current = null;
      }
      
      // Dispose of controls
      if (controlsRef.current) {
        controlsRef.current.dispose();
        controlsRef.current = null;
      }
      
      // Dispose of model and its resources
      if (modelRef.current) {
        disposeMeshes(modelRef.current);
        modelRef.current = null;
      }
      
      // Dispose of renderer
      if (rendererRef.current) {
        rendererRef.current.dispose();
        
        // Force GPU memory cleanup
        const gl = rendererRef.current.getContext();
        if (gl) {
          const loseContext = gl.getExtension('WEBGL_lose_context');
          if (loseContext) loseContext.loseContext();
        }
        
        // Remove canvas from DOM
        if (containerRef.current && rendererRef.current.domElement) {
          if (containerRef.current.contains(rendererRef.current.domElement)) {
            containerRef.current.removeChild(rendererRef.current.domElement);
          }
        }
        
        rendererRef.current = null;
      }
      
      // Clear camera reference
      cameraRef.current = null;
      
      // Clear any large objects from memory
      if (window.gc) window.gc();
    };
  }, [modelData, apiLoading, apiError, location, isTelegramMode, isMobile, devicePerformance]);
  
  // Helper function to dispose of materials and geometries recursively
  const disposeMeshes = (object) => {
    if (!object) return;
    
    if (object.dispose && typeof object.dispose === 'function') {
      object.dispose();
    }
    
          if (object.geometry) {
            object.geometry.dispose();
          }
          
          if (object.material) {
            if (Array.isArray(object.material)) {
        object.material.forEach(disposeMaterial);
            } else {
              disposeMaterial(object.material);
            }
          }
    
    if (object.children) {
      for (let i = 0; i < object.children.length; i++) {
        disposeMeshes(object.children[i]);
      }
    }
  };
  
  // Helper function to dispose of materials
  const disposeMaterial = (material) => {
    if (!material) return;
    
    // Dispose of all material properties
    Object.keys(material).forEach(prop => {
      if (material[prop] && material[prop].isTexture) {
        material[prop].dispose();
      }
    });
    
    // Common texture properties
    if (material.map) material.map.dispose();
    if (material.lightMap) material.lightMap.dispose();
    if (material.bumpMap) material.bumpMap.dispose();
    if (material.normalMap) material.normalMap.dispose();
    if (material.specularMap) material.specularMap.dispose();
    if (material.envMap) material.envMap.dispose();
    if (material.emissiveMap) material.emissiveMap.dispose();
    if (material.roughnessMap) material.roughnessMap.dispose();
    if (material.metalnessMap) material.metalnessMap.dispose();
    if (material.alphaMap) material.alphaMap.dispose();
    if (material.aoMap) material.aoMap.dispose();
    if (material.displacementMap) material.displacementMap.dispose();
    
    material.dispose();
  };

  // Helper to add debug info
  const addDebugInfo = (info) => {
    setDebugInfo(prev => `${prev}\n${info}`);
    console.log(info);
  };
  
  // Function to reset the camera view
  const resetCamera = () => {
    if (!cameraRef.current || !controlsRef.current) return;
    
    // If we have a model, adjust camera to fit it
    if (modelRef.current) {
      const box = new THREE.Box3().setFromObject(modelRef.current);
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const fov = cameraRef.current.fov * (Math.PI / 180);
      const cameraZ = Math.abs(maxDim / (2 * Math.tan(fov / 2)));
      
      cameraRef.current.position.set(cameraZ, cameraZ, cameraZ);
      cameraRef.current.lookAt(new THREE.Vector3(0, 0, 0));
    } else {
      // Default position if no model
      cameraRef.current.position.set(5, 5, 5);
      cameraRef.current.lookAt(new THREE.Vector3(0, 0, 0));
    }
    
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  };
  
  // Toggle auto-rotation
  const toggleRotation = () => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = !controlsRef.current.autoRotate;
    }
  };

  // Shared button style optimized for mobile
  const buttonStyle = {
    backgroundColor: 'rgba(0,0,0,0.6)',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    padding: isMobile ? '10px 18px' : '8px 16px', // Larger touch targets on mobile
    cursor: 'pointer',
    fontWeight: 'bold',
    fontFamily: 'Oswald, sans-serif',
    fontSize: isMobile ? '16px' : '14px', // Larger text on mobile
    touchAction: 'manipulation', // Optimize for touch
    WebkitTapHighlightColor: 'transparent', // Remove tap highlight on mobile
    userSelect: 'none' // Prevent text selection
  };

  // Handle API loading state
  if (apiLoading) {
    return (
      <div className="loading-container model-viewer-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: isMobile ? '20px' : '18px', // Larger text on mobile
        fontFamily: 'Oswald, sans-serif'
      }}>
        Loading model data...
      </div>
    );
  }

  // Handle API error state
  if (apiError) {
    return (
      <div className="error-container model-viewer-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        color: 'red',
        fontSize: isMobile ? '20px' : '18px', // Larger text on mobile
        padding: '20px',
        fontFamily: 'Oswald, sans-serif'
      }}>
        <div>Error: {apiError}</div>
        {isTelegramMode ? (
          <div style={{ 
            marginTop: '20px',
            fontSize: isMobile ? '16px' : '14px', // Larger text on mobile
            color: '#666',
            maxWidth: '600px',
            textAlign: 'center'
          }}>
            Please try uploading your file again in the Telegram bot.
          </div>
        ) : (
          <div style={{ 
            marginTop: '20px',
            fontSize: isMobile ? '16px' : '14px', // Larger text on mobile
            color: '#666',
            maxWidth: '600px',
            textAlign: 'center'
          }}>
            To view a model, add a model URL directly in the address bar: <code>?model=https://example.com/your-model.glb</code>
          </div>
        )}
      </div>
    );
  }

  // Handle missing model data
  if (!modelData) {
    return (
      <div className="no-data-container model-viewer-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: isMobile ? '20px' : '18px', // Larger text on mobile
        fontFamily: 'Oswald, sans-serif'
      }}>
        No model data available
      </div>
    );
  }

  return (
    <div className="model-viewer-container" style={{ 
      width: '100%', 
      height: '100vh', 
      position: 'relative',
      backgroundColor: '#f0f0f0',
      overflow: 'hidden',
      fontFamily: 'Oswald, sans-serif',
      // Disable pull-to-refresh on mobile
      overscrollBehavior: 'none',
      // Optimize touch behavior
      touchAction: 'none'
    }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      
      {/* Info button - now in the top left with mobile optimization */}
      <div style={{
        position: 'absolute',
        top: isMobile ? '24px' : '20px', // Move down slightly on mobile
        left: isMobile ? '24px' : '20px', // Move right slightly on mobile
        zIndex: 10
      }}>
        <button 
          onClick={() => setShowInfo(!showInfo)}
          style={buttonStyle}
        >
          {showInfo ? 'Hide Info' : 'Show Info'}
        </button>
      </div>
      
      {/* Debug button - now in the top right with mobile optimization */}
      <div style={{
        position: 'absolute',
        top: isMobile ? '24px' : '20px', // Move down slightly on mobile
        right: isMobile ? '24px' : '20px', // Move left slightly on mobile
        zIndex: 10
      }}>
        <button 
          onClick={() => setShowDebug(!showDebug)}
          style={buttonStyle}
        >
          {showDebug ? 'Hide Debug' : 'Show Debug'}
        </button>
      </div>
      
      {/* Model info - shown when info button is clicked, optimized for mobile */}
      {showInfo && (
      <div className="model-info" style={{
        position: 'absolute',
          top: isMobile ? '84px' : '70px', // Position below button on mobile
          left: isMobile ? '24px' : '20px',
        backgroundColor: 'rgba(0,0,0,0.6)',
        color: 'white',
          padding: isMobile ? '14px' : '10px', // Larger padding on mobile
        borderRadius: '4px',
          maxWidth: isMobile ? '80%' : '300px', // Wider on mobile
          fontSize: isMobile ? '16px' : '14px', // Larger text on mobile
          fontFamily: 'Oswald, sans-serif',
          zIndex: 9
      }}>
        <div><strong>Model:</strong> {modelData.model_url.split('/').pop()}</div>
        <div><strong>Type:</strong> {detectedExtension ? detectedExtension.toUpperCase() : modelData.file_extension}</div>
        {modelData.uuid && <div><strong>ID:</strong> {modelData.uuid.substring(0, 8)}...</div>}
          {isMobile && <div><strong>Device:</strong> Mobile ({devicePerformance} performance)</div>}
      </div>
      )}
      
      {modelLoading && (
        <div className="loading" style={{
          position: 'absolute', 
          top: '50%', 
          left: '50%', 
          transform: 'translate(-50%, -50%)',
          fontSize: isMobile ? '20px' : '18px', // Larger text on mobile
          color: 'white',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          padding: isMobile ? '24px' : '20px', // Larger padding on mobile
          borderRadius: '10px',
          textAlign: 'center',
          fontFamily: 'Oswald, sans-serif',
          zIndex: 100
        }}>
          <div>Loading model...</div>
          <div style={{ marginTop: '10px' }}>{loadingProgress}%</div>
          <div style={{ 
            width: isMobile ? '240px' : '200px', // Wider on mobile
            height: isMobile ? '8px' : '6px', // Taller on mobile
            backgroundColor: '#444', 
            borderRadius: '3px',
            marginTop: '10px'
          }}>
            <div style={{
              width: `${loadingProgress}%`,
              height: '100%',
              backgroundColor: '#4CAF50',
              borderRadius: '3px'
            }}></div>
          </div>
        </div>
      )}
      
      {modelError && (
        <div className="error" style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          fontSize: isMobile ? '20px' : '18px', // Larger text on mobile
          color: 'white',
          backgroundColor: 'rgba(255, 0, 0, 0.7)',
          padding: isMobile ? '24px' : '20px', // Larger padding on mobile
          borderRadius: '10px',
          textAlign: 'center',
          maxWidth: isMobile ? '90%' : '80%', // Wider on mobile
          fontFamily: 'Oswald, sans-serif',
          zIndex: 100
        }}>
          {modelError}
        </div>
      )}
      
      {showDebug && debugInfo && (
        <div className="debug" style={{
          position: 'absolute',
          bottom: '0',
          left: '0',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          padding: isMobile ? '10px' : '5px', // More padding on mobile
          fontSize: isMobile ? '14px' : '12px', // Larger text on mobile
          maxWidth: '100%',
          maxHeight: isMobile ? '50%' : '40%', // More space on mobile
          overflowY: 'auto',
          whiteSpace: 'pre-line',
          fontFamily: 'Oswald, sans-serif',
          zIndex: 8
        }}>
          {debugInfo}
        </div>
      )}
    </div>
  );
};

export default ModelViewer; 