import React from 'react';
import BackButton from './BackButton';
import '../styles/western-theme.css';

const Options = ({ volume, setVolume }) => {
  const handleVolumeChange = (e) => {
    setVolume(e.target.value / 100); // Convert to a value between 0 and 1
  };

  return (
    <div className="container">
      <BackButton />
      <h2>Options</h2>
      <div>
        <label>Sound volume</label>
        <input 
          type="range" 
          min="0" 
          max="100" 
          value={volume * 100} // Convert to a value between 0 and 100
          onChange={handleVolumeChange}
        />
        <span>{Math.round(volume * 100)}</span>
      </div>
    </div>
  );
};

export default Options;
