import os
import re

# Base URL for public-facing URLs (use environment variable or default to localhost)
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')

def get_file_extension(model_url, ext_param=None):
    """Determine file extension from URL or parameters"""
    if ext_param and ext_param.startswith('.'):
        # Use extension from URL parameter (without the dot)
        return ext_param
    else:
        # Extract from model URL
        file_extension = os.path.splitext(model_url)[1].lower()
        if not file_extension and '.' in model_url:
            # Try the last part after the dot
            file_extension = f".{model_url.split('.')[-1].lower()}"
        return file_extension if file_extension else ".glb"  # Default to .glb

def get_content_type_from_extension(file_extension):
    """Get MIME content type based on file extension"""
    if file_extension.lower().endswith('.glb'):
        return 'model/gltf-binary'
    elif file_extension.lower().endswith('.gltf'):
        return 'model/gltf+json'
    elif file_extension.lower().endswith('.fbx'):
        return 'application/octet-stream'  # FBX doesn't have an official MIME type
    elif file_extension.lower().endswith('.obj'):
        return 'text/plain'  # OBJ files are plain text
    return 'application/octet-stream'  # Default

def extract_uuid_from_text(text):
    """Extract UUID from text if present"""
    if not text:
        return None
    uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    uuid_match = re.search(uuid_pattern, text)
    return uuid_match.group(1) if uuid_match else None

def get_telegram_parameters(request, telegram_webapp=None):
    """
    Extract model parameters from Telegram WebApp or URL parameters.
    Returns a tuple of (model_url, uuid, file_extension)
    """
    model_param = request.args.get('model', '')
    uuid_param = request.args.get('uuid', '')
    ext_param = request.args.get('ext', '')
    
    # Try to get UUID from Telegram WebApp
    start_param = None
    start_command = None
    
    if telegram_webapp:
        # Extract from Telegram WebApp
        try:
            start_param = telegram_webapp.get('initDataUnsafe', {}).get('start_param')
            start_command = telegram_webapp.get('initDataUnsafe', {}).get('start_command')
        except:
            pass
            
    # If we have a direct UUID from a parameter, use that
    extracted_uuid = uuid_param
    
    # If no direct UUID, check start_param
    if not extracted_uuid and start_param:
        extracted_uuid = extract_uuid_from_text(start_param)
    
    # If still no UUID, check start_command
    if not extracted_uuid and start_command:
        extracted_uuid = extract_uuid_from_text(start_command)
    
    # If still no UUID, check if model_param contains a UUID
    if not extracted_uuid and model_param:
        extracted_uuid = extract_uuid_from_text(model_param)
    
    # Get file extension
    file_extension = get_file_extension(model_param, ext_param)
    
    # Construct model URL based on parameters
    if model_param:
        if model_param.startswith('/models/'):
            model_url = f"{BASE_URL}{model_param}"
        elif not model_param.startswith('http'):
            model_url = f"{BASE_URL}/models/{model_param}"
        else:
            model_url = model_param
    elif extracted_uuid:
        model_url = f"{BASE_URL}/models/{extracted_uuid}/model{file_extension}"
    else:
        model_url = ""
    
    return model_url, extracted_uuid, file_extension

def generate_threejs_viewer_html(model_url, file_extension, debug_mode=False, telegram_webapp_js=False):
    """
    Generates HTML with Three.js viewer for 3D models.
    Parameters:
    - model_url: URL to the 3D model
    - file_extension: File extension to determine loader type (.glb, .gltf, .fbx)
    - debug_mode: Whether to show debug info
    - telegram_webapp_js: Whether to include Telegram WebApp JS
    """
    telegram_webapp_script = '<script src="https://telegram.org/js/telegram-web-app.js"></script>' if telegram_webapp_js else ''
    
    # Normalize the extension by removing the dot if present and converting to lowercase
    extension_type = file_extension.lower().replace('.', '')
    
    # Determine appropriate loader based on file extension
    loader_type = "GLTFLoader"  # Default
    if extension_type == "fbx":
        loader_type = "FBXLoader"
    elif extension_type == "obj":
        loader_type = "OBJLoader"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>3D Model Viewer</title>
        {telegram_webapp_script}
        <style>
            body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; font-family: Arial, sans-serif; }}
            #model-container {{ width: 100%; height: 100%; }}
            .error {{ color: red; padding: 20px; position: absolute; top: 10px; left: 10px; background: rgba(255,255,255,0.8); border-radius: 5px; display: none; }}
            .debug-info {{ position: absolute; bottom: 10px; left: 10px; background: rgba(255,255,255,0.8); padding: 10px; border-radius: 5px; font-size: 12px; max-width: 80%; display: {('block' if debug_mode else 'none')}; }}
        </style>
    </head>
    <body>
        <div id="model-container"></div>
        <div id="error" class="error"></div>
        <div id="debug-info" class="debug-info"></div>
        <script src="https://unpkg.com/three@0.132.2/build/three.min.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/GLTFLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/FBXLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/OBJLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/loaders/MTLLoader.js"></script>
        <script src="https://unpkg.com/three@0.132.2/examples/js/libs/fflate.min.js"></script>
        <script>
            // Initialize debugging
            const debugInfo = document.getElementById('debug-info');
            const errorDiv = document.getElementById('error');
            
            function showDebug(text) {{
                if (debugInfo) {{
                    debugInfo.textContent += text + '\\n';
                    debugInfo.style.display = 'block';
                }}
                console.log(text);
            }}
            
            function showError(text) {{
                if (errorDiv) {{
                    errorDiv.textContent = text;
                    errorDiv.style.display = 'block';
                }}
                console.error(text);
            }}
            
            // Telegram WebApp initialization if included
            const webApp = window.Telegram?.WebApp;
            if (webApp) {{
                webApp.ready();
                webApp.expand();
                showDebug('Telegram WebApp initialized');
            }}
            
            // ThreeJS setup
            const container = document.getElementById('model-container');
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0xf0f0f0);
            
            const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.z = 5;
            
            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(window.innerWidth, window.innerHeight);
            container.appendChild(renderer.domElement);
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1);
            scene.add(directionalLight);
            
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.25;
            
            // Load 3D model
            const modelUrl = '{model_url}';
            showDebug('Model URL: ' + modelUrl);
            
            if (modelUrl) {{
                // Determine which loader to use
                const fileExtension = '{extension_type}';
                showDebug('File type: ' + fileExtension);
                
                if (fileExtension === 'fbx') {{
                    // Use FBXLoader for FBX files
                    const loader = new THREE.FBXLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
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
                            showDebug('FBX model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }} else if (fileExtension === 'obj') {{
                    // Use OBJLoader for OBJ files
                    const loader = new THREE.OBJLoader();
                    loader.load(
                        modelUrl,
                        (object) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(object);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
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
                            showDebug('OBJ model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }} else {{
                    // Use GLTFLoader for GLB/GLTF files (default)
                    const loader = new THREE.GLTFLoader();
                    loader.load(
                        modelUrl,
                        (gltf) => {{
                            // Center model
                            const box = new THREE.Box3().setFromObject(gltf.scene);
                            const center = box.getCenter(new THREE.Vector3());
                            const size = box.getSize(new THREE.Vector3());
                            
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
                            showDebug('GLTF/GLB model loaded successfully');
                        }},
                        (xhr) => {{
                            const percent = xhr.loaded / xhr.total * 100;
                            if (xhr.total > 0) {{
                                showDebug('Loading: ' + Math.round(percent) + '%');
                            }}
                        }},
                        (error) => {{
                            showError('Error loading model: ' + error.message);
                        }}
                    );
                }}
            }} else {{
                showError('No model URL provided');
            }}
            
            // Animation and resize handling
            window.addEventListener('resize', () => {{
                camera.aspect = window.innerWidth / window.innerHeight;
                camera.updateProjectionMatrix();
                renderer.setSize(window.innerWidth, window.innerHeight);
            }});
            
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }}
            
            animate();
        </script>
    </body>
    </html>
    """ 