import React from 'react';
import { useHistory } from 'react-router-dom';
import '../styles/sliding-menu.css';

const SlidingMenu = ({ isOpen, onClose, onLogOff, onInventory, onChat, onWasteland, volume, setVolume }) => {
  const history = useHistory();

  const handleOptions = () => {
    history.push('/options');
  };

  return (
    <div className={`sliding-menu ${isOpen ? 'open' : ''}`}>
      <button className="close-button" onClick={onClose}>×</button>
      <div className="menu-content">
        <button onClick={onInventory}>Inventory</button>
        <button onClick={onChat}>Chat</button>
        <button onClick={onWasteland}>Wasteland</button>
        <button onClick={handleOptions}>Options</button>
      </div>
      <div className="menu-footer">
        <button onClick={onLogOff}>Log off</button>
      </div>
    </div>
  );
};

export default SlidingMenu;