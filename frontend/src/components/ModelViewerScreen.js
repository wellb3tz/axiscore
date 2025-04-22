import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader';

const ModelViewerScreen = ({ modelUrl, onLoaded, isDarkTheme = false, accentColor = '#5e72e4' }) => {
  const mountRef = useRef(null);
  const sceneRef = useRef(new THREE.Scene());
  const controlsRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Setup scene
    const scene = sceneRef.current;
    scene.background = new THREE.Color(isDarkTheme ? 0x1c1c1c : 0xf0f0f0);
    
    // Add grid helper for empty environment
    const gridHelper = new THREE.GridHelper(10, 10, 0x888888, 0x444444);
    scene.add(gridHelper);
    
    // Setup camera
    const camera = new THREE.PerspectiveCamera(
      75, 
      window.innerWidth / window.innerHeight, 
      0.1, 
      1000
    );
    camera.position.z = 5;
    camera.position.y = 2;
    
    // Setup renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(isDarkTheme ? 0x1c1c1c : 0xf0f0f0);
    mountRef.current.appendChild(renderer.domElement);
    
    // Add lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);
    
    // Add controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controlsRef.current = controls;
    controls.enableDamping = true;
    controls.dampingFactor = 0.25;
    controls.enableZoom = true;
    
    // If no modelUrl is provided, just show the empty environment
    if (!modelUrl) {
      // Add a small coordinate axis helper
      const axesHelper = new THREE.AxesHelper(3);
      scene.add(axesHelper);
      
      // Position camera to see the grid
      camera.position.set(4, 4, 4);
      camera.lookAt(0, 0, 0);
      
      setLoading(false);
      // Call onLoaded if provided
      if (onLoaded) onLoaded();
    } else {
      // Determine file extension
      const fileExtension = modelUrl.split('.').pop().toLowerCase();
      
      setLoading(true);
      setLoadingProgress(0);
      setError(null);
      
      // Helper function to center model and adjust camera
      const setupModel = (object) => {
        // Center model
        const box = new THREE.Box3().setFromObject(object);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        
        // Reset model position to center
        object.position.x = -center.x;
        object.position.y = -center.y;
        object.position.z = -center.z;
        
        // Adjust camera
        const maxDim = Math.max(size.x, size.y, size.z);
        const fov = camera.fov * (Math.PI / 180);
        const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
        
        camera.position.z = cameraDistance * 1.5;
        camera.updateProjectionMatrix();
        
        scene.add(object);
        setLoading(false);
        // Call onLoaded if provided
        if (onLoaded) onLoaded();
      };
      
      // Progress and error handlers for all loaders
      const onProgress = (xhr) => {
        if (xhr.lengthComputable) {
          const percentComplete = Math.round((xhr.loaded / xhr.total) * 100);
          setLoadingProgress(percentComplete);
          console.log(percentComplete + '% loaded');
        }
      };
      
      const onError = (error) => {
        console.error('Error loading model:', error);
        
        // Try to provide more helpful error messages
        let errorMessage = error.message || 'Failed to load model';
        
        if (errorMessage.includes('NetworkError') || errorMessage.includes('CORS')) {
          errorMessage = 'Network error: The model could not be loaded due to CORS or server issues. Please try again later.';
        } else if (errorMessage.includes('404')) {
          errorMessage = 'Model not found: The 3D model file could not be found on the server.';
        } else if (errorMessage.includes('500')) {
          errorMessage = 'Server error: There was a problem processing the 3D model on our servers.';
        }
        
        setError(errorMessage);
        setLoading(false);
        // Call onLoaded even on error to hide the main loading spinner
        if (onLoaded) onLoaded();
      };
      
      // Load the model based on file extension
      if (fileExtension === 'fbx') {
        // Use FBXLoader for FBX files
        const loader = new FBXLoader();
        loader.load(
          modelUrl,
          setupModel,
          onProgress,
          onError
        );
      } else if (fileExtension === 'obj') {
        // Use OBJLoader for OBJ files
        const loader = new OBJLoader();
        loader.load(
          modelUrl,
          setupModel,
          onProgress,
          onError
        );
      } else {
        // Use GLTFLoader for GLB/GLTF files (default)
        const loader = new GLTFLoader();
        loader.load(
          modelUrl,
          (gltf) => {
            setupModel(gltf.scene);
          },
          onProgress,
          onError
        );
      }
    }
    
    // Handle window resize
    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };
    
    window.addEventListener('resize', handleResize);
    
    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);
      
      if (controlsRef.current) {
        controlsRef.current.update();
      }
      
      renderer.render(scene, camera);
    };
    
    animate();
    
    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (mountRef.current && mountRef.current.contains(renderer.domElement)) {
        mountRef.current.removeChild(renderer.domElement);
      }
    };
  }, [modelUrl, isDarkTheme, onLoaded]);
  
  const textColor = isDarkTheme ? '#ffffff' : '#333333';
  
  return (
    <div ref={mountRef} style={{ width: '100%', height: '100vh', position: 'relative' }}>
      {loading && modelUrl && (
        <div style={{
          position: 'absolute',
          bottom: '20px',
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: isDarkTheme ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.9)',
          color: textColor,
          padding: '10px 20px',
          borderRadius: '20px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          zIndex: 100,
          transition: 'opacity 0.3s ease',
          fontSize: '14px'
        }}>
          <div style={{
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            border: `2px solid ${isDarkTheme ? '#333' : '#e9ecef'}`,
            borderTopColor: accentColor,
            animation: 'model-spin 1s linear infinite'
          }}></div>
          <div>
            <div style={{ fontWeight: '500' }}>Loading 3D Model</div>
            {loadingProgress > 0 && (
              <div style={{ fontSize: '12px', opacity: 0.8 }}>{loadingProgress}% complete</div>
            )}
          </div>
          <style>{`
            @keyframes model-spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}
      
      {error && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          backgroundColor: isDarkTheme ? 'rgba(30,30,30,0.9)' : 'rgba(255,255,255,0.9)',
          color: textColor,
          padding: '20px',
          borderRadius: '12px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
          maxWidth: '80%',
          textAlign: 'center',
          zIndex: 100
        }}>
          <div style={{ marginBottom: '16px' }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#f5365c" strokeWidth="2" style={{ margin: '0 auto' }}>
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </div>
          <h3 style={{ margin: '0 0 10px 0', fontWeight: '600' }}>Error Loading Model</h3>
          <p style={{ margin: 0, opacity: 0.8 }}>{error}</p>
        </div>
      )}
      
      <style>{`
        canvas {
          outline: none;
        }
      `}</style>
    </div>
  );
};

export default ModelViewerScreen; 