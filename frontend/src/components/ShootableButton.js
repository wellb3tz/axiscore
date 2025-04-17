import React, { useState } from 'react';
import '../styles/shootable-button.css';
import gunshotSound from '../sounds/gunshot.mp3'; // Ensure you have this sound file

const ShootableButton = ({ onClick, children }) => {
  const [isShattered, setIsShattered] = useState(false);

  const handleShot = (e) => {
    const btn = e.currentTarget;
    const rect = btn.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Play gunshot sound
    const audio = new Audio(gunshotSound);
    audio.play();

    // Create bullet hole
    const hole = document.createElement('div');
    hole.className = 'bullet-hole';
    hole.style.left = `${x}px`;
    hole.style.top = `${y}px`;
    btn.appendChild(hole);

    // Create shatter pieces
    for (let i = 0; i < 8; i++) {
      const piece = document.createElement('div');
      piece.className = 'shatter-piece';
      piece.style.setProperty('--tx', (Math.random() - 0.5) * 100 + 'px');
      piece.style.setProperty('--ty', (Math.random() - 0.5) * 100 + 'px');
      piece.style.setProperty('--rot', Math.random() * 360 + 'deg');
      piece.style.animation = `shatter 0.5s forwards ${i * 0.1}s`;
      btn.appendChild(piece);
    }

    // Fade out button
    setTimeout(() => {
      setIsShattered(true);
      setTimeout(() => {
        setIsShattered(false);
      }, 1000); // Adjust time as needed
    }, 500);

    // Call the onClick handler
    if (onClick) {
      onClick(e);
    }
  };

  return (
    <button className="shootable-button" onClick={handleShot} style={{ display: isShattered ? 'none' : 'block' }}>
      {children}
    </button>
  );
};

export default ShootableButton;