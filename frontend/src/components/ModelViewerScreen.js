import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';

const ModelViewerScreen = ({ modelUrl }) => {
  const mountRef = useRef(null);
  const sceneRef = useRef(new THREE.Scene());
  const controlsRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Setup scene
    const scene = sceneRef.current;
    scene.background = new THREE.Color(0xf0f0f0);
    
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
    renderer.setClearColor(0xf0f0f0);
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
    } else {
      // Load the 3D model
      const loader = new GLTFLoader();
      
      setLoading(true);
      setError(null);
      
      loader.load(
        modelUrl,
        (gltf) => {
          // Center model
          const box = new THREE.Box3().setFromObject(gltf.scene);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());
          
          // Reset model position to center
          gltf.scene.position.x = -center.x;
          gltf.scene.position.y = -center.y;
          gltf.scene.position.z = -center.z;
          
          // Adjust camera
          const maxDim = Math.max(size.x, size.y, size.z);
          const fov = camera.fov * (Math.PI / 180);
          const cameraDistance = maxDim / (2 * Math.tan(fov / 2));
          
          camera.position.z = cameraDistance * 1.5;
          camera.updateProjectionMatrix();
          
          scene.add(gltf.scene);
          setLoading(false);
        },
        (xhr) => {
          // Loading progress
          console.log((xhr.loaded / xhr.total) * 100 + '% loaded');
        },
        (error) => {
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
        }
      );
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
  }, [modelUrl]);
  
  return (
    <div ref={mountRef} style={{ width: '100%', height: '100vh', position: 'relative' }}>
      {loading && (
        <div className="loading">
          <div className="loading-spinner"></div>
          <span>Loading model...</span>
        </div>
      )}
      {error && (
        <div className="error-message">
          {error}
        </div>
      )}
      {!modelUrl && !loading && (
        <div className="empty-environment-message" style={{
          position: 'absolute',
          bottom: '20px',
          left: '20px',
          color: '#333',
          background: 'rgba(255, 255, 255, 0.7)',
          padding: '10px',
          borderRadius: '5px',
          fontSize: '14px'
        }}>
          No model loaded. Send a 3D model to the bot to view it here.
        </div>
      )}
    </div>
  );
};

export default ModelViewerScreen; 