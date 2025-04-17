import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import * as THREE from 'three';

const ParticleSystem = forwardRef(({ scene }, ref) => {
  const spriteRef = useRef(null);
  const frameTextures = useRef([]);
  const currentFrame = useRef(0);
  const totalFrames = 30;
  const frameDuration = 40;

  useEffect(() => {
    const textureLoader = new THREE.TextureLoader();
    const frames = [];
    for (let i = 1; i < totalFrames; i++) {
      frames.push(textureLoader.load(`https://raw.githubusercontent.com/wellb3tz/theQuickandtheDead/main/frontend/media/frame${i}.png`));
    }
    frameTextures.current = frames;

    const spriteMaterial = new THREE.SpriteMaterial({ 
      map: frames[0],
      depthTest: false,
      depthWrite: false
    });

    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.visible = false;
    sprite.renderOrder = 999; // Ensure sprites render on top
    scene.add(sprite);
    spriteRef.current = sprite;
  }, [scene]);

  useImperativeHandle(ref, () => ({
    triggerParticles(position) {
      if (spriteRef.current) {
        spriteRef.current.position.copy(position);
        spriteRef.current.visible = true;
        currentFrame.current = 0;

        const animateSprite = () => {
          if (currentFrame.current < totalFrames) {
            if (spriteRef.current && frameTextures.current[currentFrame.current]) {
              spriteRef.current.material.map = frameTextures.current[currentFrame.current];
              spriteRef.current.material.needsUpdate = true;
              currentFrame.current++;
              setTimeout(animateSprite, frameDuration);
            }
          } else {
            if (spriteRef.current) {
              spriteRef.current.visible = false;
            }
          }
        };
        animateSprite();
      }
    }
  }));

  return null;
});

export default ParticleSystem;