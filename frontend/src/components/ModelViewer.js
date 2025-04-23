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
  
  // State to track model loading
  const [loadingProgress, setLoadingProgress] = useState(0);

  // Three.js objects
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);
  const modelRef = useRef(null);

  // Detect Telegram environment
  const isTelegramMode = location.pathname.includes('miniapp') || 
                         (typeof window !== 'undefined' && window.Telegram?.WebApp);

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
    
    // Add a grid to help with orientation
    const gridHelper = new THREE.GridHelper(20, 20, 0x888888, 0x444444);
    scene.add(gridHelper);
    
    // Add axes helper for orientation
    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);
    
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
    const extension = file_extension?.toLowerCase().replace('.', '') || 
                      modelUrl.split('.').pop().toLowerCase();
    
    addDebugInfo(`Loading model: ${modelUrl}`);
    addDebugInfo(`Using file extension: ${extension}`);

    let loader;
    switch (extension) {
      case 'fbx':
        loader = new FBXLoader();
        break;
      case 'obj':
        loader = new OBJLoader();
        break;
      case 'glb':
      case 'gltf':
      default:
        loader = new GLTFLoader();
        break;
    }
    
    const onProgress = (xhr) => {
      if (xhr.lengthComputable) {
        const percentComplete = (xhr.loaded / xhr.total) * 100;
        setLoadingProgress(Math.round(percentComplete));
        addDebugInfo(`Loading: ${Math.round(percentComplete)}%`);
      }
    };

    // Load the model
    try {
      loader.load(
        modelUrl,
        // On load success
        (object) => {
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

          // Make sure all materials receive shadows
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

          // Center model
          const box = new THREE.Box3().setFromObject(model);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());

          model.position.x = -center.x;
          model.position.y = -center.y;
          model.position.z = -center.z;

          // Adjust camera position based on model size
          const maxDim = Math.max(size.x, size.y, size.z);
          const fov = camera.fov * (Math.PI / 180);
          const cameraZ = Math.abs(maxDim / (2 * Math.tan(fov / 2)));
          
          camera.position.set(cameraZ, cameraZ, cameraZ);
          camera.lookAt(new THREE.Vector3(0, 0, 0));
          
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
          
          // If in Telegram WebApp, notify it's ready
          if (isTelegramMode && window.Telegram?.WebApp) {
            window.Telegram.WebApp.MainButton.setText('Model Loaded');
            window.Telegram.WebApp.MainButton.show();
            window.Telegram.WebApp.MainButton.onClick(() => {
              window.Telegram.WebApp.MainButton.hide();
            });
          }
        },
        // On progress
        onProgress,
        // On error
        (error) => {
          console.error('Error loading model:', error);
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
      );
    } catch (err) {
      console.error('Exception during model loading:', err);
      setModelError(`Exception during model loading: ${err.message}`);
      setModelLoading(false);
    }

    // Animation loop
    const animate = () => {
      const animationId = requestAnimationFrame(animate);
      if (controlsRef.current) {
        controlsRef.current.update();
      }
      if (rendererRef.current && sceneRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
      return animationId;
    };
    
    const animationId = animate();

    // Cleanup function
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);
      
      // Dispose of Three.js resources
      if (sceneRef.current) {
        sceneRef.current.traverse((object) => {
          if (object.geometry) {
            object.geometry.dispose();
          }
          
          if (object.material) {
            if (Array.isArray(object.material)) {
              object.material.forEach(material => disposeMaterial(material));
            } else {
              disposeMaterial(object.material);
            }
          }
        });
      }
      
      if (rendererRef.current) {
        if (containerRef.current) {
          containerRef.current.removeChild(rendererRef.current.domElement);
        }
        rendererRef.current.dispose();
      }
    };
  }, [modelData, apiLoading, apiError, location, isTelegramMode]);
  
  // Helper function to dispose of materials
  const disposeMaterial = (material) => {
    if (material.map) material.map.dispose();
    if (material.lightMap) material.lightMap.dispose();
    if (material.bumpMap) material.bumpMap.dispose();
    if (material.normalMap) material.normalMap.dispose();
    if (material.specularMap) material.specularMap.dispose();
    if (material.envMap) material.envMap.dispose();
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

  // Handle API loading state
  if (apiLoading) {
    return (
      <div className="loading-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: '18px'
      }}>
        Loading model data...
      </div>
    );
  }

  // Handle API error state
  if (apiError) {
    return (
      <div className="error-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        color: 'red',
        fontSize: '18px',
        padding: '20px'
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
      <div className="no-data-container" style={{
        width: '100%', 
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontSize: '18px'
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
      overflow: 'hidden'
    }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      
      {/* Camera controls */}
      <div className="camera-controls" style={{
        position: 'absolute',
        bottom: '20px',
        right: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        <button 
          onClick={resetCamera}
          style={{
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            padding: '8px 16px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          Reset View
        </button>
        <button 
          onClick={toggleRotation}
          style={{
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            padding: '8px 16px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          Toggle Rotation
        </button>
        <button 
          onClick={() => setShowDebug(!showDebug)}
          style={{
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            padding: '8px 16px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          {showDebug ? 'Hide Debug' : 'Show Debug'}
        </button>
      </div>
      
      {/* Model info */}
      <div className="model-info" style={{
        position: 'absolute',
        top: '10px',
        left: '10px',
        backgroundColor: 'rgba(0,0,0,0.6)',
        color: 'white',
        padding: '10px',
        borderRadius: '4px',
        maxWidth: '300px',
        fontSize: '14px'
      }}>
        <div><strong>Model:</strong> {modelData.model_url.split('/').pop()}</div>
        <div><strong>Type:</strong> {modelData.file_extension}</div>
        {modelData.uuid && <div><strong>ID:</strong> {modelData.uuid.substring(0, 8)}...</div>}
      </div>
      
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
          textAlign: 'center'
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
          maxWidth: '80%'
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
          whiteSpace: 'pre-line'
        }}>
          {debugInfo}
        </div>
      )}
      
      {/* Help text */}
      <div className="help-text" style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        backgroundColor: 'rgba(0,0,0,0.6)',
        color: 'white',
        padding: '10px',
        borderRadius: '4px',
        maxWidth: '300px',
        fontSize: '12px'
      }}>
        <div>Left click + drag: Rotate</div>
        <div>Right click + drag: Pan</div>
        <div>Scroll: Zoom</div>
      </div>
    </div>
  );
};

export default ModelViewer; 