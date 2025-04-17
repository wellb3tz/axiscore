import React, { useState, useEffect } from 'react';
import BackButton from './BackButton';
import '../styles/inventory.css';

const Inventory = () => {
  const [items, setItems] = useState([]);
  const [username, setUsername] = useState('');
  const [gridItems, setGridItems] = useState(Array(64).fill(null)); // State to track items in each grid slot

  useEffect(() => {
    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      setUsername(storedUsername);
    }

    fetch('https://thequickandthedead.onrender.com/inventory?user_id=1')
      .then(response => response.json())
      .then(data => setItems(data));
  }, []);

  const handleItemPlacement = (index, item) => {
    const newGridItems = [...gridItems];
    newGridItems[index] = item;
    setGridItems(newGridItems);
  };

  return (
    <div className="container">
      <BackButton />
      <h2>Inventory of {username}</h2>
      <div className="inventory-layout">
        <div className="equipped-items">
          <div className="slot">
            <label>Head</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="slot">
            <label>Body</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="slot">
            <label>Left Arm</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="slot">
            <label>Right Arm</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="slot">
            <label>Legs</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="slot">
            <label>Feet</label>
            <select>
              <option value="">Select Item</option>
              {items.map((item, index) => (
                <option key={index} value={item}>{item}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="all-items">
          <h3>All items</h3>
          <div className="grid">
            {gridItems.map((gridItem, index) => (
              <div key={index} className="grid-slot" onClick={() => handleItemPlacement(index, 'Item')}>
                {gridItem}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Inventory;