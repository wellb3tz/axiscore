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

  // Three.js objects
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const controlsRef = useRef(null);

  // Step 1: Fetch model data from the API
  useEffect(() => {
    const fetchModelData = async () => {
      try {
        // Get parameters from URL
        const params = new URLSearchParams(location.search);
        const modelParam = params.get('model');
        const uuidParam = params.get('uuid');
        const extParam = params.get('ext');
        let apiEndpoint = '/viewer'; // Default to viewer endpoint

        if (location.pathname.includes('miniapp')) {
          apiEndpoint = '/miniapp';
        } else if (location.pathname.includes('view')) {
          apiEndpoint = '/view';
        }

        // Add any parameters to the request
        if (modelParam || uuidParam) {
          const queryParams = new URLSearchParams();
          if (modelParam) queryParams.append('model', modelParam);
          if (uuidParam) queryParams.append('uuid', uuidParam);
          if (extParam) queryParams.append('ext', extParam);
          apiEndpoint += `?${queryParams.toString()}`;
        }

        addDebugInfo(`Fetching model data from: ${apiEndpoint}`);

        // Fetch data from backend API
        const response = await fetch(apiEndpoint);
        if (!response.ok) {
          throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        setModelData(data);
        addDebugInfo(`Model data received: ${JSON.stringify(data)}`);
      } catch (err) {
        console.error('Error fetching model data:', err);
        setApiError(err.message);
        addDebugInfo(`API Error: ${err.message}`);
      } finally {
        setApiLoading(false);
      }
    };

    fetchModelData();
  }, [location]);

  // Step 2: Initialize and render the 3D model
  useEffect(() => {
    if (!modelData || apiLoading || apiError) return;

    const { model_url, file_extension, base_url, uuid } = modelData;
    let modelUrl = model_url;
    const isTelegramMode = location.pathname.includes('miniapp') || (typeof window !== 'undefined' && window.Telegram?.WebApp);
    const baseUrl = base_url || window.location.origin;

    // Initialize Telegram WebApp if needed
    if (isTelegramMode && window.Telegram?.WebApp) {
      const webApp = window.Telegram.WebApp;
      webApp.ready();
      webApp.expand();

      // Extract parameters from Telegram if needed
      const startParam = webApp.initDataUnsafe?.start_param;
      addDebugInfo(`Telegram WebApp detected! Start param: ${startParam || 'none'}`);

      // If no model URL is provided but we have a start param that might be a UUID, 
      // construct a model URL
      if ((!modelUrl || modelUrl === '') && startParam && startParam.includes('-')) {
        modelUrl = `${baseUrl}/models/${startParam}/model${file_extension}`;
        addDebugInfo(`Using model from Telegram parameter: ${modelUrl}`);
      }
    }

    if (!modelUrl) {
      setModelError('No model URL provided. Please provide a valid 3D model URL.');
      setModelLoading(false);
      return;
    }

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
    camera.position.z = 5;
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controlsRef.current = controls;

    // Handle window resize
    const handleResize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
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

          // Center model
          const box = new THREE.Box3().setFromObject(model);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());

          model.position.x = -center.x;
          model.position.y = -center.y;
          model.position.z = -center.z;

          // Adjust camera position based on model size
          const maxDim = Math.max(size.x, size.y, size.z);
          camera.position.z = maxDim * 2;
          camera.updateProjectionMatrix();

          scene.add(model);
        },
        // On progress
        (xhr) => {
          const percent = xhr.loaded / xhr.total * 100;
          if (xhr.total > 0) {
            addDebugInfo(`Loading: ${Math.round(percent)}%`);
          }
        },
        // On error
        (error) => {
          console.error('Error loading model:', error);
          setModelError(`Failed to load 3D model: ${error.message}`);
          setModelLoading(false);
          addDebugInfo(`Error: ${error.message}`);
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
      if (rendererRef.current) {
        container.removeChild(rendererRef.current.domElement);
        rendererRef.current.dispose();
      }
    };
  }, [modelData, apiLoading, apiError, location]);

  // Helper to add debug info
  const addDebugInfo = (info) => {
    setDebugInfo(prev => `${prev}\n${info}`);
    console.log(info);
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
        justifyContent: 'center',
        alignItems: 'center',
        color: 'red',
        fontSize: '18px'
      }}>
        Error: {apiError}
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
    <div className="model-viewer-container" style={{ width: '100%', height: '100vh', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      
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
          Loading model...
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
      
      {debugInfo && (
        <div className="debug" style={{
          position: 'absolute',
          bottom: '0',
          left: '0',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          color: 'white',
          padding: '5px',
          fontSize: '12px',
          maxWidth: '100%',
          maxHeight: '30%',
          overflowY: 'auto',
          whiteSpace: 'pre-line'
        }}>
          {debugInfo}
        </div>
      )}
    </div>
  );
};

export default ModelViewer; 