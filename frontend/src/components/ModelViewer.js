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
    
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(5, 5, 5); // Position camera at an angle for better initial view
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    // Ambient light for general illumination
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    // Directional light with shadows
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 10, 7);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 1024;
    directionalLight.shadow.mapSize.height = 1024;
    scene.add(directionalLight);
    
    // Add a hemisphere light for more natural lighting
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.6);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.enableZoom = true;
    controls.enablePan = true;
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
        if (modelUrl.includes('fbx')) {
          extension = 'fbx';
          setDetectedExtension('fbx');
          addDebugInfo(`Detected FBX model from URL pattern`);
        } else if (modelUrl.includes('obj')) {
          extension = 'obj';
          setDetectedExtension('obj');
          addDebugInfo(`Detected OBJ model from URL pattern`);
        } else if (modelUrl.includes('gltf')) {
          extension = 'gltf';
          setDetectedExtension('gltf');
          addDebugInfo(`Detected GLTF model from URL pattern`);
        } else if (modelUrl.includes('glb')) {
          extension = 'glb';
          setDetectedExtension('glb');
          addDebugInfo(`Detected GLB model from URL pattern`);
        }
      }
    }
    
    addDebugInfo(`Loading model: ${modelUrl}`);
    addDebugInfo(`Using file extension: ${extension}`);

    let loader;
    switch (extension) {
      case 'fbx':
        loader = new FBXLoader();
        addDebugInfo('Using FBXLoader for FBX file');
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

      // Apply standard processing to all model types
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

      // Reset model position and rotation for consistency
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

      // Place camera at a standardized position based on model bounds
      const fov = camera.fov * (Math.PI / 180);
      const cameraDistance = Math.max(
        scaledSize.x,
        scaledSize.y,
        scaledSize.z
      ) / (2 * Math.tan(fov / 2));
      
      // Adjust camera position based on model type for consistency
      const cameraZ = cameraDistance * 1.5; // Add some padding
      
      // Set camera to a consistent position for all model types
      camera.position.set(cameraZ, cameraZ, cameraZ);
      camera.lookAt(new THREE.Vector3(0, 0, 0));
      addDebugInfo(`Camera position set to: ${cameraZ.toFixed(2)}, ${cameraZ.toFixed(2)}, ${cameraZ.toFixed(2)}`);
      
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
          
          if (isJsonError && extension === 'glb' && modelUrl.includes('.fbx')) {
            // Try FBX loader as fallback
            addDebugInfo('JSON parse error detected. Trying FBXLoader as fallback...');
            setDetectedExtension('fbx');
            const fbxLoader = new FBXLoader();
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
            addDebugInfo(`Error: ${error.message}`);
            
            // If loading fails, provide suggestions
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

    // Animation loop
    const animate = () => {
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

    // Cleanup function - Improved unmounting
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
    };
  }, [modelData, apiLoading, apiError, location, isTelegramMode]);
  
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

  // Shared button style
  const buttonStyle = {
    backgroundColor: 'rgba(0,0,0,0.6)',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    padding: '8px 16px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontFamily: 'Oswald, sans-serif',
    fontSize: '14px'
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
        fontSize: '18px',
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
        fontSize: '18px',
        padding: '20px',
        fontFamily: 'Oswald, sans-serif'
      }}>
        <div>Error: {apiError}</div>
        {isTelegramMode ? (
          <div style={{ 
            marginTop: '20px',
            fontSize: '14px',
            color: '#666',
            maxWidth: '600px',
            textAlign: 'center'
          }}>
            Please try uploading your file again in the Telegram bot.
          </div>
        ) : (
          <div style={{ 
            marginTop: '20px',
            fontSize: '14px',
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
        fontSize: '18px',
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
      fontFamily: 'Oswald, sans-serif'
    }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      
      {/* Info button - now in the top left */}
      <div style={{
        position: 'absolute',
        top: '20px',
        left: '20px'
      }}>
        <button 
          onClick={() => setShowInfo(!showInfo)}
          style={buttonStyle}
        >
          {showInfo ? 'Hide Info' : 'Show Info'}
        </button>
      </div>
      
      {/* Debug button - now in the top right */}
      <div style={{
        position: 'absolute',
        top: '20px',
        right: '20px'
      }}>
        <button 
          onClick={() => setShowDebug(!showDebug)}
          style={buttonStyle}
        >
          {showDebug ? 'Hide Debug' : 'Show Debug'}
        </button>
      </div>
      
      {/* Model info - shown when info button is clicked */}
      {showInfo && (
        <div className="model-info" style={{
          position: 'absolute',
          top: '70px',
          left: '20px',
          backgroundColor: 'rgba(0,0,0,0.6)',
          color: 'white',
          padding: '10px',
          borderRadius: '4px',
          maxWidth: '300px',
          fontSize: '14px',
          fontFamily: 'Oswald, sans-serif'
        }}>
          <div><strong>Model:</strong> {modelData.model_url.split('/').pop()}</div>
          <div><strong>Type:</strong> {detectedExtension ? detectedExtension.toUpperCase() : modelData.file_extension}</div>
          {modelData.uuid && <div><strong>ID:</strong> {modelData.uuid.substring(0, 8)}...</div>}
        </div>
      )}
      
      {modelLoading && (
        <div className="loading" style={{
          position: 'absolute', 
          top: '50%', 
          left: '50%', 
          transform: 'translate(-50%, -50%)',
          fontSize: '18px',
          color: 'white',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          padding: '20px',
          borderRadius: '10px',
          textAlign: 'center',
          fontFamily: 'Oswald, sans-serif'
        }}>
          <div>Loading model...</div>
          <div style={{ marginTop: '10px' }}>{loadingProgress}%</div>
          <div style={{ 
            width: '200px', 
            height: '6px', 
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
          fontSize: '18px',
          color: 'white',
          backgroundColor: 'rgba(255, 0, 0, 0.7)',
          padding: '20px',
          borderRadius: '10px',
          textAlign: 'center',
          maxWidth: '80%',
          fontFamily: 'Oswald, sans-serif'
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
          padding: '5px',
          fontSize: '12px',
          maxWidth: '100%',
          maxHeight: '40%',
          overflowY: 'auto',
          whiteSpace: 'pre-line',
          fontFamily: 'Oswald, sans-serif'
        }}>
          {debugInfo}
        </div>
      )}
    </div>
  );
};

export default ModelViewer; 