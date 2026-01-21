// API Configuration
const API_BASE = 'http://localhost:8000';

// State
let selectedCharacter = null;
let currentCombatSession = null;
let awaitingPlayerAction = null;
let cachedSpells = [];
let cachedAbilities = [];
let cachedConsumables = [];
let cachedStatusEffects = [];

// XP thresholds for leveling
const XP_THRESHOLDS = [0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000];

// ==================== Utility Functions ====================

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, options);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

function showModal(content) {
    const modal = document.getElementById('modal');
    document.getElementById('modalBody').innerHTML = content;
    modal.classList.add('show');
}

function closeModal() {
    document.getElementById('modal').classList.remove('show');
}

function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
}

function getXpForNextLevel(level) {
    if (level >= 20) return null;
    return XP_THRESHOLDS[level];
}

function getXpProgress(experience, level) {
    const currentThreshold = XP_THRESHOLDS[level - 1] || 0;
    const nextThreshold = XP_THRESHOLDS[level] || experience;
    const progress = experience - currentThreshold;
    const needed = nextThreshold - currentThreshold;
    return { progress, needed, percent: Math.min(100, (progress / needed) * 100) };
}

// ==================== Connection Check ====================

async function checkConnection() {
    const status = document.getElementById('connectionStatus');
    const dot = status.querySelector('.status-dot');
    const text = status.querySelector('.status-text');

    try {
        await apiCall('/health');
        dot.className = 'status-dot connected';
        text.textContent = 'API Connected';
        return true;
    } catch (e) {
        dot.className = 'status-dot disconnected';
        text.textContent = 'API Disconnected';
        return false;
    }
}

// ==================== Tab Navigation ====================

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(tab.dataset.tab).classList.add('active');

        loadTabData(tab.dataset.tab);
    });
});

function loadTabData(tabName) {
    switch (tabName) {
        case 'characters':
            loadCharacters();
            populateCharacterSelects();
            loadMonsterSelect();
            break;
        case 'inventory':
            loadItems();
            populateCharacterSelects();
            break;
        case 'location':
            loadZones();
            populateCharacterSelects();
            loadTerrainLegend();
            break;
        case 'quests':
            loadQuests();
            populateCharacterSelects();
            break;
        case 'combat':
            loadCombatCharacters();
            loadCombatZones();
            break;
        case 'scenarios':
            loadScenarios();
            populateCharacterSelects();
            break;
        case 'reference':
            loadBaseWeapons();
            loadBaseArmor();
            loadSpells();
            loadConsumables();
            loadStatusEffects();
            loadClassAbilities();
            loadTerrainEffects();
            loadMonsters();
            break;
        case 'events':
            loadEvents();
            populateCharacterSelects();
            break;
    }
}

// ==================== Characters ====================

async function loadCharacters() {
    try {
        const filter = document.getElementById('filterCharType').value;
        let endpoint = '/character/';
        if (filter) {
            endpoint += `?character_type=${filter}`;
        }

        const characters = await apiCall(endpoint);
        const container = document.getElementById('charactersList');

        if (characters.length === 0) {
            container.innerHTML = '<p class="placeholder">No characters found</p>';
            return;
        }

        container.innerHTML = characters.map(char => `
            <div class="list-item ${selectedCharacter?.id === char.id ? 'selected' : ''}">
                <div class="list-item-content" onclick="selectCharacter(${char.id})">
                    <div class="list-item-header">
                        <span class="list-item-title">${char.name}</span>
                        <span class="list-item-badge ${char.character_type}">${char.character_type}</span>
                    </div>
                    <div class="list-item-subtitle">
                        Level ${char.level} ${capitalize(char.character_class)} | HP: ${char.current_hp}/${char.max_hp}
                    </div>
                </div>
                <button class="btn btn-small btn-danger list-item-delete" onclick="event.stopPropagation(); deleteCharacter(${char.id})" title="Delete ${char.name}">✕</button>
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function selectCharacter(id) {
    try {
        const char = await apiCall(`/character/${id}`);
        selectedCharacter = char;

        // Update visual selection in the list
        document.querySelectorAll('#charactersList .list-item').forEach(item => {
            item.classList.remove('selected');
        });
        const selectedItem = document.querySelector(`#charactersList .list-item-content[onclick*="selectCharacter(${id})"]`);
        if (selectedItem) {
            selectedItem.closest('.list-item')?.classList.add('selected');
        }

        const skills = await apiCall(`/character/${id}/skills`);
        const details = document.getElementById('characterDetails');
        const hpPercent = Math.round((char.current_hp / char.max_hp) * 100);
        const xpInfo = getXpProgress(char.experience, char.level);
        const canLevelUp = char.level < 20 && char.experience >= getXpForNextLevel(char.level);

        // Format spell slots
        let spellSlotsHtml = '<span class="placeholder">No spell slots</span>';
        if (char.spell_slots && Object.keys(char.spell_slots).length > 0) {
            spellSlotsHtml = Object.entries(char.spell_slots).map(([level, slots]) => `
                <div class="spell-slot-level">
                    <div class="level">Level ${level}</div>
                    <div class="slots">${slots.current}/${slots.max}</div>
                </div>
            `).join('');
        }

        // Format ability uses
        let abilityUsesHtml = '<span class="placeholder">No abilities</span>';
        if (char.ability_uses && Object.keys(char.ability_uses).length > 0) {
            abilityUsesHtml = Object.entries(char.ability_uses).map(([abilityId, uses]) => `
                <div class="ability-use-item ${uses > 0 ? 'available' : 'exhausted'}">
                    ${abilityId.replace(/_/g, ' ')}: ${uses}
                </div>
            `).join('');
        }

        details.innerHTML = `
            <div class="char-detail-section">
                <div class="char-name-class">
                    <h3>${char.name}</h3>
                    <span class="list-item-badge">${capitalize(char.character_class)}</span>
                </div>
                <div>Level ${char.level} ${capitalize(char.character_type)} | Status: ${capitalize(char.status)}</div>
                <div class="gold-display">
                    <span class="gold-icon">$</span>
                    <span>${char.gold} Gold</span>
                </div>
            </div>

            <div class="char-detail-section">
                <h4>Experience</h4>
                <div class="xp-bar">
                    <div class="xp-bar-fill" style="width: ${xpInfo.percent}%">
                        ${char.experience} / ${char.level < 20 ? getXpForNextLevel(char.level) : 'MAX'} XP
                    </div>
                </div>
                ${canLevelUp ? `<button class="btn btn-primary btn-small" onclick="levelUpCharacter(${char.id})" style="margin-top:0.5rem;">Level Up!</button>` : ''}
            </div>

            <div class="char-detail-section">
                <h4>Health</h4>
                <div class="health-bar ${char.status === 'unconscious' ? 'unconscious' : ''} ${char.status === 'dead' ? 'dead' : ''}">
                    <div class="health-bar-fill" style="width: ${hpPercent}%">
                        ${char.current_hp} / ${char.max_hp}
                    </div>
                </div>
                <div style="font-size: 0.875rem; color: var(--text-secondary);">
                    Temp HP: ${char.temporary_hp} | AC: ${char.armor_class}
                </div>
                ${char.status === 'unconscious' ? `
                <div class="death-saves">
                    <div class="death-save-row">
                        <span class="death-save-label">Death Saves:</span>
                        <span class="death-save-successes">
                            ${[0,1,2].map(i => `<span class="death-save-marker ${i < char.death_save_successes ? 'success' : ''}">✓</span>`).join('')}
                        </span>
                        <span class="death-save-failures">
                            ${[0,1,2].map(i => `<span class="death-save-marker ${i < char.death_save_failures ? 'failure' : ''}">✗</span>`).join('')}
                        </span>
                    </div>
                    ${char.is_stable ? '<div class="stable-indicator">Stabilized</div>' : ''}
                </div>
                ` : ''}
                ${char.status === 'dead' ? '<div class="dead-indicator">DEAD</div>' : ''}
            </div>

            <div class="char-detail-section">
                <h4>Attributes</h4>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">STR</div>
                        <div class="stat-value">${char.strength}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">DEX</div>
                        <div class="stat-value">${char.dexterity}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">CON</div>
                        <div class="stat-value">${char.constitution}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">INT</div>
                        <div class="stat-value">${char.intelligence}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">WIS</div>
                        <div class="stat-value">${char.wisdom}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">CHA</div>
                        <div class="stat-value">${char.charisma}</div>
                    </div>
                </div>
            </div>

            <div class="char-detail-section">
                <h4>Spell Slots</h4>
                <div class="spell-slots">${spellSlotsHtml}</div>
            </div>

            <div class="char-detail-section">
                <h4>Ability Uses</h4>
                <div class="ability-uses">${abilityUsesHtml}</div>
            </div>

            <div class="char-detail-section">
                <h4>Location</h4>
                <div>Zone: ${char.zone_id || 'None'} | Position: (${char.x}, ${char.y})</div>
            </div>

            <div class="char-detail-section">
                <h4>Skills</h4>
                <div class="skill-list">
                    ${skills.length > 0
                        ? skills.map(s => `<span class="skill-tag">${s.name} (Lv.${s.level})</span>`).join('')
                        : '<span class="placeholder">No skills</span>'}
                </div>
            </div>

            <div class="rest-buttons">
                <button class="btn btn-rest short" onclick="restCharacter(${char.id}, 'short')">Short Rest</button>
                <button class="btn btn-rest" onclick="restCharacter(${char.id}, 'long')">Long Rest</button>
            </div>

            <div class="char-actions">
                <button class="btn btn-secondary" onclick="editCharacter(${char.id})">Edit</button>
                <button class="btn btn-secondary" onclick="addSkillModal(${char.id})">Add Skill</button>
                <button class="btn btn-danger" onclick="deleteCharacter(${char.id})">Delete</button>
            </div>
        `;
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function restCharacter(charId, restType) {
    try {
        await apiCall(`/character/${charId}/rest?rest_type=${restType}`, 'POST');
        showToast(`${capitalize(restType)} rest completed!`);
        selectCharacter(charId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function levelUpCharacter(charId) {
    try {
        const result = await apiCall(`/character/${charId}/level-up`, 'POST');
        showToast(`Leveled up to ${result.new_level}! HP: +${result.hp_increase}`);
        selectCharacter(charId);
        loadCharacters();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

document.getElementById('createCharacterForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    try {
        const char = await apiCall('/character/', 'POST', {
            name: document.getElementById('charName').value,
            character_class: document.getElementById('charClass').value,
            character_type: document.getElementById('charType').value,
        });

        showToast(`Created ${char.name}!`);
        e.target.reset();
        loadCharacters();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

async function deleteCharacter(id) {
    if (!confirm('Are you sure you want to delete this character?')) return;

    try {
        await apiCall(`/character/${id}`, 'DELETE');
        showToast('Character deleted');
        selectedCharacter = null;
        document.getElementById('characterDetails').innerHTML = '<p class="placeholder">Select a character to view details</p>';
        loadCharacters();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function addSkillModal(charId) {
    showModal(`
        <h2>Add Skill</h2>
        <form onsubmit="addSkill(event, ${charId})">
            <div class="form-group">
                <label>Skill Name</label>
                <input type="text" id="newSkillName" required>
            </div>
            <div class="form-group">
                <label>Level</label>
                <input type="number" id="newSkillLevel" value="1" min="1">
            </div>
            <button type="submit" class="btn btn-primary">Add Skill</button>
        </form>
    `);
}

async function addSkill(e, charId) {
    e.preventDefault();

    try {
        await apiCall(`/character/${charId}/skills`, 'POST', {
            name: document.getElementById('newSkillName').value,
            level: parseInt(document.getElementById('newSkillLevel').value),
        });

        showToast('Skill added!');
        closeModal();
        selectCharacter(charId);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Inventory ====================

function formatItemProperties(item) {
    const props = item.properties || {};
    let propsStr = '';

    if (item.item_type === 'weapon') {
        const dice = props.damage_dice || '1d4';
        const hit = props.hit_bonus || 0;
        propsStr = `${dice}${hit > 0 ? ` +${hit}` : ''}`;
    } else if (item.item_type === 'armor') {
        const ac = props.armor_bonus || 0;
        propsStr = `AC +${ac}`;
    } else if (item.item_type === 'consumable') {
        const effect = props.effect_type || 'misc';
        propsStr = capitalize(effect);
    }

    return propsStr;
}

async function showItemDetails(itemId) {
    try {
        const item = await apiCall(`/items/${itemId}`);
        const props = item.properties || {};

        let propsHtml = '';
        if (item.item_type === 'weapon') {
            propsHtml = `
                <p><strong>Damage:</strong> ${props.damage_dice || '1d4'}</p>
                <p><strong>Hit Bonus:</strong> +${props.hit_bonus || 0}</p>
                ${props.range ? `<p><strong>Range:</strong> ${props.range}</p>` : ''}
            `;
        } else if (item.item_type === 'armor') {
            propsHtml = `
                <p><strong>AC Bonus:</strong> +${props.armor_bonus || 0}</p>
            `;
        } else if (item.item_type === 'consumable') {
            propsHtml = `
                <p><strong>Effect:</strong> ${capitalize(props.effect_type || 'misc')}</p>
                ${props.heal_amount ? `<p><strong>Heal Amount:</strong> ${props.heal_amount}</p>` : ''}
                ${props.damage_amount ? `<p><strong>Damage:</strong> ${props.damage_amount}</p>` : ''}
            `;
        }

        showModal(`
            <h2>${item.name}</h2>
            <p><span class="list-item-badge ${item.rarity}">${item.rarity}</span> ${capitalize(item.item_type)}</p>
            <p>${item.description || 'No description'}</p>
            <hr>
            <p><strong>Weight:</strong> ${item.weight}</p>
            <p><strong>Value:</strong> ${item.value} gold</p>
            ${propsHtml}
            <hr>
            <button class="btn btn-danger" onclick="deleteItem(${item.id})">Delete Item</button>
        `);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteItem(itemId) {
    if (!confirm('Delete this item?')) return;

    try {
        await apiCall(`/items/${itemId}`, 'DELETE');
        showToast('Item deleted!');
        closeModal();
        loadItems();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadItems() {
    try {
        const items = await apiCall('/items/');
        const container = document.getElementById('itemsList');

        if (items.length === 0) {
            container.innerHTML = '<p class="placeholder">No items found</p>';
            return;
        }

        container.innerHTML = items.map(item => {
            const propsStr = formatItemProperties(item);
            return `
                <div class="list-item" onclick="showItemDetails(${item.id})">
                    <div class="list-item-header">
                        <span class="list-item-title">${item.name}</span>
                        <span class="list-item-badge ${item.rarity}">${item.rarity}</span>
                    </div>
                    <div class="list-item-subtitle">
                        ${capitalize(item.item_type)}${propsStr ? ` (${propsStr})` : ''} | ${item.value} gold
                    </div>
                </div>
            `;
        }).join('');

        const addSelect = document.getElementById('addItemSelect');
        addSelect.innerHTML = '<option value="">-- Select Item --</option>' +
            items.map(i => `<option value="${i.id}">${i.name}</option>`).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

document.getElementById('itemType').addEventListener('change', (e) => {
    const type = e.target.value;
    document.getElementById('weaponProps').style.display = type === 'weapon' ? 'block' : 'none';
    document.getElementById('armorProps').style.display = type === 'armor' ? 'block' : 'none';
});

document.getElementById('createItemForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const itemType = document.getElementById('itemType').value;
    const properties = {};

    if (itemType === 'weapon') {
        properties.damage_dice = document.getElementById('weaponDamageDice').value;
        properties.hit_bonus = parseInt(document.getElementById('weaponHitBonus').value);
    } else if (itemType === 'armor') {
        properties.armor_bonus = parseInt(document.getElementById('armorBonus').value);
    }

    try {
        const item = await apiCall('/items/', 'POST', {
            name: document.getElementById('itemName').value,
            item_type: itemType,
            rarity: document.getElementById('itemRarity').value,
            weight: parseFloat(document.getElementById('itemWeight').value),
            value: parseInt(document.getElementById('itemValue').value),
            description: document.getElementById('itemDesc').value || null,
            properties: properties,
        });

        showToast(`Created ${item.name}!`);
        e.target.reset();
        document.getElementById('weaponProps').style.display = 'block';
        document.getElementById('armorProps').style.display = 'none';
        loadItems();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

async function loadCharacterInventory() {
    const charId = document.getElementById('invCharSelect').value;
    const display = document.getElementById('inventoryDisplay');
    const addSection = document.getElementById('addItemSection');

    if (!charId) {
        display.innerHTML = '<p class="placeholder">Select a character</p>';
        addSection.style.display = 'none';
        return;
    }

    try {
        const inventory = await apiCall(`/character/${charId}/inventory`);
        addSection.style.display = 'block';

        if (inventory.length === 0) {
            display.innerHTML = '<p class="placeholder">Inventory is empty</p>';
            return;
        }

        display.innerHTML = inventory.map(inv => `
            <div class="inventory-item ${inv.equipped ? 'equipped' : ''}">
                <div class="inventory-item-name">${inv.item.name}</div>
                <div class="inventory-item-qty">
                    Qty: ${inv.quantity}
                    ${inv.equipped ? `<br>Equipped: ${inv.equipment_slot}` : ''}
                </div>
                <div style="margin-top: 0.5rem;">
                    ${!inv.equipped
                        ? `<button class="btn btn-small" onclick="equipItem(${charId}, ${inv.id})">Equip</button>`
                        : `<button class="btn btn-small" onclick="unequipItem(${charId}, ${inv.id})">Unequip</button>`
                    }
                    <button class="btn btn-small btn-danger" onclick="removeItem(${charId}, ${inv.id})">Drop</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function addItemToInventory() {
    const charId = document.getElementById('invCharSelect').value;
    const itemId = document.getElementById('addItemSelect').value;
    const qty = parseInt(document.getElementById('addItemQty').value);

    if (!charId || !itemId) {
        showToast('Select a character and item', 'error');
        return;
    }

    try {
        await apiCall(`/character/${charId}/inventory`, 'POST', {
            item_id: parseInt(itemId),
            quantity: qty,
        });

        showToast('Item added to inventory!');
        loadCharacterInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function equipItem(charId, invItemId) {
    const slot = prompt('Enter equipment slot (e.g., main_hand, chest, head):');
    if (!slot) return;

    try {
        await apiCall(`/character/${charId}/inventory/${invItemId}/equip`, 'POST', {
            equipment_slot: slot,
        });

        showToast('Item equipped!');
        loadCharacterInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function unequipItem(charId, invItemId) {
    try {
        await apiCall(`/character/${charId}/inventory/${invItemId}/unequip`, 'POST');
        showToast('Item unequipped!');
        loadCharacterInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function removeItem(charId, invItemId) {
    if (!confirm('Remove this item from inventory?')) return;

    try {
        await apiCall(`/character/${charId}/inventory/${invItemId}`, 'DELETE');
        showToast('Item removed!');
        loadCharacterInventory();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Location ====================

const TERRAIN_COLORS = {
    grass: '#22c55e',
    stone: '#6b7280',
    water: '#3b82f6',
    forest: '#166534',
    mountain: '#44403c',
    sand: '#fbbf24',
    swamp: '#4d7c0f',
    lava: '#dc2626',
    ice: '#67e8f9',
    void: '#18181b',
};

function loadTerrainLegend() {
    const legend = document.getElementById('terrainLegend');
    if (!legend) return;

    legend.innerHTML = Object.entries(TERRAIN_COLORS).map(([type, color]) => `
        <div class="terrain-legend-item">
            <div class="terrain-legend-color" style="background: ${color}"></div>
            <span>${capitalize(type)}</span>
        </div>
    `).join('');
}

async function loadZones() {
    try {
        const zones = await apiCall('/location/zones');
        const container = document.getElementById('zonesList');

        if (zones.length === 0) {
            container.innerHTML = '<p class="placeholder">No zones found</p>';
            return;
        }

        container.innerHTML = zones.map(zone => `
            <div class="list-item" onclick="selectZone(${zone.id})">
                <div class="list-item-title">${zone.name}</div>
                <div class="list-item-subtitle">${zone.width}x${zone.height} grid</div>
            </div>
        `).join('');

        const selects = ['mapZoneSelect', 'moveZoneSelect', 'combatZoneSelect'];
        selects.forEach(id => {
            const select = document.getElementById(id);
            if (select) {
                select.innerHTML = '<option value="">-- Select Zone --</option>' +
                    zones.map(z => `<option value="${z.id}">${z.name}</option>`).join('');
            }
        });
    } catch (e) {
        showToast(e.message, 'error');
    }
}

document.getElementById('createZoneForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    try {
        const zone = await apiCall('/location/zones', 'POST', {
            name: document.getElementById('zoneName').value,
            width: parseInt(document.getElementById('zoneWidth').value),
            height: parseInt(document.getElementById('zoneHeight').value),
            description: document.getElementById('zoneDesc').value || null,
        });

        showToast(`Created ${zone.name}!`);
        e.target.reset();
        loadZones();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

async function loadZoneMap() {
    const zoneId = document.getElementById('mapZoneSelect').value;
    const mapContainer = document.getElementById('zoneMap');

    if (!zoneId) {
        mapContainer.innerHTML = '';
        return;
    }

    try {
        const zone = await apiCall(`/location/zones/${zoneId}`);
        const characters = await apiCall(`/location/characters?zone_id=${zoneId}`);
        const items = await apiCall(`/location/items?zone_id=${zoneId}`);

        const charPositions = {};
        characters.forEach(c => {
            charPositions[`${c.x},${c.y}`] = c;
        });

        const itemPositions = {};
        items.forEach(i => {
            itemPositions[`${i.ground_x},${i.ground_y}`] = i;
        });

        const displayWidth = Math.min(zone.width, 30);
        const displayHeight = Math.min(zone.height, 30);

        mapContainer.style.gridTemplateColumns = `repeat(${displayWidth}, 20px)`;

        // Get grid cells for terrain
        let gridCells = {};
        try {
            const cells = await apiCall(`/location/zones/${zoneId}/cells`);
            cells.forEach(c => {
                gridCells[`${c.x},${c.y}`] = c;
            });
        } catch (e) {
            // Cells might not exist
        }

        let html = '';
        for (let y = 0; y < displayHeight; y++) {
            for (let x = 0; x < displayWidth; x++) {
                const key = `${x},${y}`;
                const hasChar = charPositions[key];
                const hasItem = itemPositions[key];
                const cell = gridCells[key];
                const terrain = cell?.terrain_type || 'grass';

                let cellClass = `map-cell terrain-${terrain}`;
                let content = '';

                if (hasChar) {
                    cellClass += ' has-character';
                    content = hasChar.name[0];
                } else if (hasItem) {
                    cellClass += ' has-item';
                    content = '!';
                }

                html += `<div class="${cellClass}" onclick="showCellInfo(${zoneId}, ${x}, ${y})" title="(${x},${y}) - ${terrain}">${content}</div>`;
            }
        }

        mapContainer.innerHTML = html;
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function showCellInfo(zoneId, x, y) {
    try {
        const data = await apiCall('/location/surroundings', 'POST', {
            zone_id: zoneId,
            x: x,
            y: y,
            radius: 0,
        });

        const info = document.getElementById('locationInfo');
        let html = `<strong>Position (${x}, ${y})</strong><br>`;

        if (data.characters.length > 0) {
            html += `<br>Characters: ${data.characters.map(c => c.name).join(', ')}`;
        }

        if (data.items.length > 0) {
            html += `<br>Items: ${data.items.map(i => i.name).join(', ')}`;
        }

        if (data.cells.length > 0) {
            html += `<br>Terrain: ${data.cells[0].terrain_type}`;
        }

        info.innerHTML = html;
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function moveCharacter() {
    const charId = document.getElementById('moveCharSelect').value;
    const zoneId = document.getElementById('moveZoneSelect').value;
    const x = parseInt(document.getElementById('moveX').value);
    const y = parseInt(document.getElementById('moveY').value);
    const resultDiv = document.getElementById('moveResult');

    if (!charId) {
        showToast('Select a character', 'error');
        return;
    }

    try {
        // Use the new move endpoint with terrain effects
        const params = new URLSearchParams({ x, y });
        if (zoneId) params.append('zone_id', zoneId);

        const result = await apiCall(`/character/${charId}/move?${params.toString()}`, 'POST');

        if (result.blocked) {
            resultDiv.className = 'move-result blocked';
            resultDiv.innerHTML = `<strong>Movement Blocked!</strong><br>${result.block_reason}`;
            showToast('Movement blocked', 'error');
        } else if (result.damage_taken > 0) {
            resultDiv.className = 'move-result damage';
            resultDiv.innerHTML = `
                <strong>Moved to (${x}, ${y})</strong><br>
                Terrain: ${result.terrain_effect?.name || 'Unknown'}<br>
                <span style="color: var(--accent-danger)">Took ${result.damage_taken} ${result.damage_type || ''} damage!</span>
                ${result.status_effects_applied?.length ? `<br>Applied: ${result.status_effects_applied.join(', ')}` : ''}
            `;
            showToast(`Moved! Took ${result.damage_taken} damage from terrain.`, 'success');
        } else {
            resultDiv.className = 'move-result success';
            resultDiv.innerHTML = `
                <strong>Moved to (${x}, ${y})</strong><br>
                Movement cost: ${result.movement_cost}
                ${result.terrain_effect ? `<br>Terrain: ${result.terrain_effect.name}` : ''}
            `;
            showToast('Character moved!', 'success');
        }

        loadZoneMap();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Quests ====================

async function loadQuests() {
    try {
        const quests = await apiCall('/quests/');
        const container = document.getElementById('questsList');

        if (quests.length === 0) {
            container.innerHTML = '<p class="placeholder">No quests found</p>';
            return;
        }

        container.innerHTML = quests.map(quest => `
            <div class="list-item" onclick="selectQuest(${quest.id})">
                <div class="list-item-header">
                    <span class="list-item-title">${quest.title}</span>
                    <span class="list-item-badge">Lv.${quest.level_requirement}</span>
                </div>
                <div class="list-item-subtitle">
                    ${quest.objectives.length} objectives | ${quest.experience_reward} XP, ${quest.gold_reward} gold
                </div>
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

let selectedQuest = null;

function selectQuest(id) {
    selectedQuest = id;
    const charId = document.getElementById('questCharSelect').value;

    const actions = document.getElementById('questActions');
    actions.innerHTML = `
        <p>Quest #${id} selected</p>
        ${charId ? `
            <button class="btn btn-primary" onclick="assignQuest(${id}, ${charId})">Assign to Character</button>
        ` : '<p class="placeholder">Select a character first</p>'}
    `;
}

document.getElementById('createQuestForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const objectives = [];
    document.querySelectorAll('#objectivesList .objective-row').forEach(row => {
        const desc = row.querySelector('.obj-desc').value;
        const count = parseInt(row.querySelector('.obj-count').value);
        if (desc) {
            objectives.push({ description: desc, target_count: count });
        }
    });

    try {
        const quest = await apiCall('/quests/', 'POST', {
            title: document.getElementById('questTitle').value,
            description: document.getElementById('questDesc').value || null,
            level_requirement: parseInt(document.getElementById('questLevel').value),
            experience_reward: parseInt(document.getElementById('questXP').value),
            gold_reward: parseInt(document.getElementById('questGold').value),
            objectives: objectives,
        });

        showToast(`Created quest: ${quest.title}!`);
        e.target.reset();
        document.getElementById('objectivesList').innerHTML = `
            <div class="objective-row">
                <input type="text" placeholder="Objective description" class="obj-desc">
                <input type="number" value="1" min="1" class="obj-count" style="width:60px;">
            </div>
        `;
        loadQuests();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

function addObjectiveRow() {
    const container = document.getElementById('objectivesList');
    const row = document.createElement('div');
    row.className = 'objective-row';
    row.innerHTML = `
        <input type="text" placeholder="Objective description" class="obj-desc">
        <input type="number" value="1" min="1" class="obj-count" style="width:60px;">
    `;
    container.appendChild(row);
}

async function loadCharacterQuests() {
    const charId = document.getElementById('questCharSelect').value;
    const container = document.getElementById('characterQuestsList');

    if (!charId) {
        container.innerHTML = '<p class="placeholder">Select a character</p>';
        return;
    }

    try {
        const assignments = await apiCall(`/quests/character/${charId}`);

        if (assignments.length === 0) {
            container.innerHTML = '<p class="placeholder">No assigned quests</p>';
            return;
        }

        container.innerHTML = assignments.map(a => `
            <div class="list-item">
                <div class="list-item-header">
                    <span class="list-item-title">${a.quest.title}</span>
                    <span class="list-item-badge">${a.status}</span>
                </div>
                <div style="margin-top: 0.5rem;">
                    ${a.objectives_progress.map(obj => `
                        <div style="font-size: 0.875rem; margin: 0.25rem 0;">
                            ${obj.completed ? '✅' : '⬜'} ${obj.description}
                            (${obj.current_count}/${obj.target_count})
                            ${!obj.completed && a.status === 'active' ? `
                                <button class="btn btn-small" onclick="updateProgress(${a.quest_id}, ${charId}, ${obj.objective_id})">+1</button>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
                ${a.status === 'active' ? `
                    <div style="margin-top: 0.5rem;">
                        <button class="btn btn-small btn-primary" onclick="completeQuest(${a.quest_id}, ${charId})">Complete</button>
                        <button class="btn btn-small btn-danger" onclick="abandonQuest(${a.quest_id}, ${charId})">Abandon</button>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function assignQuest(questId, charId) {
    try {
        await apiCall(`/quests/${questId}/assign`, 'POST', {
            character_id: charId,
        });

        showToast('Quest assigned!');
        loadCharacterQuests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function updateProgress(questId, charId, objectiveId) {
    try {
        await apiCall(`/quests/${questId}/progress?character_id=${charId}`, 'POST', {
            objective_id: objectiveId,
            amount: 1,
        });

        loadCharacterQuests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function completeQuest(questId, charId) {
    try {
        await apiCall(`/quests/${questId}/complete?character_id=${charId}`, 'POST');
        showToast('Quest completed!');
        loadCharacterQuests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function abandonQuest(questId, charId) {
    if (!confirm('Abandon this quest?')) return;

    try {
        await apiCall(`/quests/${questId}/abandon?character_id=${charId}`, 'POST');
        showToast('Quest abandoned');
        loadCharacterQuests();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Combat ====================

async function loadCombatZones() {
    try {
        const zones = await apiCall('/location/zones');
        const select = document.getElementById('combatZoneSelect');
        if (select) {
            select.innerHTML = '<option value="">-- No Zone (no terrain/range) --</option>' +
                zones.map(z => `<option value="${z.id}">${z.name}</option>`).join('');
        }
    } catch (e) {
        // Ignore
    }
}

async function loadCombatCharacters() {
    try {
        const characters = await apiCall('/character/');

        const team1 = document.getElementById('team1Select');
        const team2 = document.getElementById('team2Select');

        const players = characters.filter(c => c.character_type === 'player');
        const npcs = characters.filter(c => c.character_type === 'npc');

        team1.innerHTML = players.map(c => `
            <div class="team-member" data-id="${c.id}" onclick="toggleTeamMember(this)">
                ${c.name} (Lv.${c.level} ${capitalize(c.character_class)})
            </div>
        `).join('') || '<p class="placeholder">No players</p>';

        team2.innerHTML = npcs.map(c => `
            <div class="team-member" data-id="${c.id}" onclick="toggleTeamMember(this)">
                ${c.name} (Lv.${c.level} ${capitalize(c.character_class)})
            </div>
        `).join('') || '<p class="placeholder">No NPCs</p>';

        // Pre-load combat resources
        await Promise.all([
            loadCombatSpells(),
            loadCombatAbilities(),
        ]);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadCombatSpells() {
    try {
        cachedSpells = await apiCall('/reference/spells');
    } catch (e) {
        cachedSpells = [];
    }
}

async function loadCombatAbilities() {
    try {
        cachedAbilities = await apiCall('/reference/abilities');
    } catch (e) {
        cachedAbilities = [];
    }
}

function toggleTeamMember(element) {
    element.classList.toggle('selected');
}

document.getElementById('startCombatForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const zoneId = document.getElementById('combatZoneSelect').value;
    const initiativeType = document.getElementById('initiativeTypeSelect')?.value || 'individual';
    const team1Members = Array.from(document.querySelectorAll('#team1Select .team-member.selected'))
        .map(el => ({ character_id: parseInt(el.dataset.id), team_id: 1 }));
    const team2Members = Array.from(document.querySelectorAll('#team2Select .team-member.selected'))
        .map(el => ({ character_id: parseInt(el.dataset.id), team_id: 2 }));

    const participants = [...team1Members, ...team2Members];

    if (participants.length < 2) {
        showToast('Select at least 2 combatants', 'error');
        return;
    }

    try {
        const payload = { participants, initiative_type: initiativeType };
        if (zoneId) payload.zone_id = parseInt(zoneId);

        const combat = await apiCall('/combat/start', 'POST', payload);

        currentCombatSession = combat.id;
        showToast('Combat started!');
        document.getElementById('combatLog').innerHTML = '';
        updateCombatDisplay(combat);
        document.getElementById('combatArena').style.display = 'block';
        document.getElementById('combatStatus').innerHTML = '';
    } catch (e) {
        showToast(e.message, 'error');
    }
});

function formatStatusEffects(statusEffects) {
    if (!statusEffects || Object.keys(statusEffects).length === 0) return '';

    return `<div class="status-effects">
        ${Object.entries(statusEffects).map(([effect, duration]) => {
            const harmful = ['poisoned', 'burning', 'stunned', 'paralyzed', 'blinded', 'frightened', 'slowed', 'cursed'].includes(effect);
            const beneficial = ['hasted', 'invisible', 'blessed', 'regenerating', 'defending', 'dodging'].includes(effect);
            const type = harmful ? 'harmful' : (beneficial ? 'beneficial' : 'neutral');
            return `<span class="status-effect-tag ${type}">${effect} (${duration})</span>`;
        }).join('')}
    </div>`;
}

function updateCombatDisplay(data) {
    document.getElementById('combatRound').textContent = `Round: ${data.round_number}`;
    document.getElementById('combatTurn').textContent = `Turn: ${data.current_turn + 1}`;
    document.getElementById('combatState').textContent = `Status: ${data.status}`;

    const combatants = data.combatants || [];
    const team1 = combatants.filter(c => c.team_id === 1);
    const team2 = combatants.filter(c => c.team_id === 2);

    const currentId = data.current_combatant?.id || data.awaiting_player?.id;

    document.querySelector('#team1Display .combatants').innerHTML = team1.map(c => `
        <div class="combatant-card ${c.id === currentId ? 'current-turn' : ''} ${!c.is_alive ? 'dead' : ''}">
            <div class="combatant-name">
                <span>${c.name}</span>
                <span>Init: ${c.initiative}</span>
            </div>
            <div class="health-bar" style="height: 1rem; margin: 0.5rem 0;">
                <div class="health-bar-fill" style="width: ${(c.current_hp / c.max_hp) * 100}%"></div>
            </div>
            <div class="combatant-hp">HP: ${c.current_hp}/${c.max_hp} | AC: ${c.armor_class}</div>
            ${formatStatusEffects(c.status_effects)}
        </div>
    `).join('');

    document.querySelector('#team2Display .combatants').innerHTML = team2.map(c => `
        <div class="combatant-card ${c.id === currentId ? 'current-turn' : ''} ${!c.is_alive ? 'dead' : ''}">
            <div class="combatant-name">
                <span>${c.name}</span>
                <span>Init: ${c.initiative}</span>
            </div>
            <div class="health-bar" style="height: 1rem; margin: 0.5rem 0;">
                <div class="health-bar-fill" style="width: ${(c.current_hp / c.max_hp) * 100}%"></div>
            </div>
            <div class="combatant-hp">HP: ${c.current_hp}/${c.max_hp} | AC: ${c.armor_class}</div>
            ${formatStatusEffects(c.status_effects)}
        </div>
    `).join('');

    const playerActions = document.getElementById('playerActions');
    const processBtn = document.getElementById('processBtn');
    const finishBtn = document.getElementById('finishBtn');

    if (data.status === 'awaiting_player' && data.awaiting_player) {
        awaitingPlayerAction = data.awaiting_player;
        playerActions.style.display = 'block';
        processBtn.style.display = 'none';

        document.getElementById('currentTurnInfo').innerHTML = `
            <strong>${data.awaiting_player.name}'s Turn</strong>
        `;

        // Populate targets (enemies)
        const enemies = combatants.filter(c => c.team_id !== data.awaiting_player.team_id && c.is_alive);
        const allAllies = combatants.filter(c => c.team_id === data.awaiting_player.team_id && c.is_alive);

        document.getElementById('attackTarget').innerHTML = enemies.map(e =>
            `<option value="${e.id}">${e.name} (HP: ${e.current_hp})</option>`
        ).join('');

        // Populate spell targets (enemies + allies for heals)
        document.getElementById('spellTarget').innerHTML =
            '<option value="">-- Self --</option>' +
            enemies.map(e => `<option value="${e.id}">[Enemy] ${e.name}</option>`).join('') +
            allAllies.map(a => `<option value="${a.id}">[Ally] ${a.name}</option>`).join('');

        // Populate ability targets
        document.getElementById('abilityTarget').innerHTML =
            '<option value="">-- Self/None --</option>' +
            enemies.map(e => `<option value="${e.id}">[Enemy] ${e.name}</option>`).join('') +
            allAllies.map(a => `<option value="${a.id}">[Ally] ${a.name}</option>`).join('');

        // Populate item targets
        document.getElementById('itemTarget').innerHTML =
            '<option value="">-- Self --</option>' +
            allAllies.map(a => `<option value="${a.id}">${a.name}</option>`).join('');

        // Load character-specific spells
        loadCharacterSpells(data.awaiting_player.character_id);
        loadCharacterAbilities(data.awaiting_player.character_id);
        loadCharacterConsumables(data.awaiting_player.character_id);
    } else {
        playerActions.style.display = 'none';
        processBtn.style.display = 'inline-block';
        awaitingPlayerAction = null;

        if (data.current_combatant) {
            document.getElementById('currentTurnInfo').innerHTML = `
                <strong>${data.current_combatant.name}'s Turn</strong>
            `;
        }
    }

    if (data.combat_ended || data.status === 'finished') {
        processBtn.style.display = 'none';
        finishBtn.style.display = 'inline-block';
        playerActions.style.display = 'none';

        document.getElementById('currentTurnInfo').innerHTML = `
            <strong>Combat Ended!</strong>
        `;
    }
}

async function loadCharacterSpells(charId) {
    try {
        const char = await apiCall(`/character/${charId}`);
        const charClass = char.character_class;

        // Filter spells by class
        const availableSpells = cachedSpells.filter(s =>
            s.classes && s.classes.includes(charClass)
        );

        const spellSelect = document.getElementById('spellChoice');
        spellSelect.innerHTML = '<option value="">-- Select Spell --</option>' +
            availableSpells.map(s => `<option value="${s.id}">${s.name} (Lv.${s.level})</option>`).join('');
    } catch (e) {
        // Ignore
    }
}

async function loadCharacterAbilities(charId) {
    try {
        const char = await apiCall(`/character/${charId}`);
        const charClass = char.character_class;

        // Filter abilities by class
        const availableAbilities = cachedAbilities.filter(a =>
            a.class === charClass && (a.min_level || 1) <= char.level
        );

        const abilitySelect = document.getElementById('abilityChoice');
        abilitySelect.innerHTML = '<option value="">-- Select Ability --</option>' +
            availableAbilities.map(a => {
                const uses = char.ability_uses?.[a.id] || 0;
                return `<option value="${a.id}" ${uses <= 0 ? 'disabled' : ''}>${a.name} (${uses} uses)</option>`;
            }).join('');
    } catch (e) {
        // Ignore
    }
}

async function loadCharacterConsumables(charId) {
    try {
        const inventory = await apiCall(`/character/${charId}/inventory`);
        const consumables = inventory.filter(inv => inv.item.item_type === 'consumable');

        const itemSelect = document.getElementById('itemChoice');
        itemSelect.innerHTML = '<option value="">-- Select Item --</option>' +
            consumables.map(inv => `<option value="${inv.id}">${inv.item.name} (x${inv.quantity})</option>`).join('');
    } catch (e) {
        // Ignore
    }
}

async function processCombat() {
    if (!currentCombatSession) return;

    try {
        const result = await apiCall(`/combat/${currentCombatSession}/process`, 'POST');

        if (result.actions_taken) {
            result.actions_taken.forEach(action => {
                addCombatLogEntry(action);
            });
        }

        updateCombatDisplay(result);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function hideAllActionSelects() {
    document.getElementById('targetSelect').style.display = 'none';
    document.getElementById('spellSelect').style.display = 'none';
    document.getElementById('abilitySelect').style.display = 'none';
    document.getElementById('itemSelect').style.display = 'none';
}

function playerAction(actionType) {
    hideAllActionSelects();

    switch (actionType) {
        case 'attack':
            document.getElementById('targetSelect').style.display = 'flex';
            break;
        case 'spell':
            document.getElementById('spellSelect').style.display = 'flex';
            break;
        case 'ability':
            document.getElementById('abilitySelect').style.display = 'flex';
            break;
        case 'item':
            document.getElementById('itemSelect').style.display = 'flex';
            break;
        default:
            executePlayerAction(actionType);
    }
}

function confirmAttack() {
    const targetId = parseInt(document.getElementById('attackTarget').value);
    executePlayerAction('attack', targetId);
    hideAllActionSelects();
}

async function confirmSpell() {
    const spellId = document.getElementById('spellChoice').value;
    const targetId = document.getElementById('spellTarget').value;

    if (!spellId) {
        showToast('Select a spell', 'error');
        return;
    }

    try {
        const payload = {
            character_id: awaitingPlayerAction.character_id,
            action_type: 'spell',
            spell_id: spellId,
        };
        if (targetId) payload.target_id = parseInt(targetId);

        const result = await apiCall(`/combat/${currentCombatSession}/act`, 'POST', payload);
        addCombatLogEntry(result.action);
        hideAllActionSelects();
        await processCombat();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function confirmAbility() {
    const abilityId = document.getElementById('abilityChoice').value;
    const targetId = document.getElementById('abilityTarget').value;

    if (!abilityId) {
        showToast('Select an ability', 'error');
        return;
    }

    try {
        const payload = {
            character_id: awaitingPlayerAction.character_id,
            action_type: 'ability',
            ability_id: abilityId,
        };
        if (targetId) payload.target_id = parseInt(targetId);

        const result = await apiCall(`/combat/${currentCombatSession}/act`, 'POST', payload);
        addCombatLogEntry(result.action);
        hideAllActionSelects();
        await processCombat();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function confirmItem() {
    const itemId = document.getElementById('itemChoice').value;
    const targetId = document.getElementById('itemTarget').value;

    if (!itemId) {
        showToast('Select an item', 'error');
        return;
    }

    try {
        const payload = {
            character_id: awaitingPlayerAction.character_id,
            action_type: 'item',
            inventory_item_id: parseInt(itemId),
        };
        if (targetId) payload.target_id = parseInt(targetId);

        const result = await apiCall(`/combat/${currentCombatSession}/act`, 'POST', payload);
        addCombatLogEntry(result.action);
        hideAllActionSelects();
        await processCombat();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function executePlayerAction(actionType, targetId = null) {
    if (!awaitingPlayerAction) return;

    try {
        const payload = {
            character_id: awaitingPlayerAction.character_id,
            action_type: actionType,
        };

        if (targetId) {
            payload.target_id = targetId;
        }

        const result = await apiCall(`/combat/${currentCombatSession}/act`, 'POST', payload);

        addCombatLogEntry(result.action);

        await processCombat();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function addCombatLogEntry(action) {
    const log = document.getElementById('combatLog');
    let className = '';

    if (action.critical) className = 'critical';
    else if (action.hit === true) className = 'hit';
    else if (action.hit === false) className = 'miss';

    // Add type-specific classes
    const actionType = action.action_type?.toLowerCase() || '';
    if (actionType.includes('spell')) className += ' spell';
    else if (actionType.includes('ability')) className += ' ability';
    else if (actionType.includes('item')) className += ' item';
    else if (action.description?.toLowerCase().includes('heal')) className += ' heal';

    log.innerHTML = `<div class="log-entry ${className}">[R${action.round_number}] ${action.description}</div>` + log.innerHTML;
}

async function finishCombat() {
    if (!currentCombatSession) return;

    try {
        const summary = await apiCall(`/combat/${currentCombatSession}/finish`, 'POST');

        const loot = summary.loot || { gold: 0, items: [] };
        const lootHtml = loot.gold > 0 || (loot.items && loot.items.length > 0)
            ? `
                <h3>Loot Obtained</h3>
                ${loot.gold > 0 ? `<p><span class="gold-icon">$</span> ${loot.gold} Gold</p>` : ''}
                ${loot.items && loot.items.length > 0
                    ? loot.items.map(item => `<p>• ${item.item_name} x${item.quantity}</p>`).join('')
                    : ''
                }
            `
            : '';

        showModal(`
            <h2>Combat Summary</h2>
            <p><strong>Winner:</strong> Team ${summary.winner_team_id}</p>
            <p><strong>Rounds:</strong> ${summary.total_rounds}</p>
            <p><strong>Actions:</strong> ${summary.total_actions}</p>
            <h3>Experience Earned</h3>
            ${Object.entries(summary.experience_by_character || {}).map(([charId, xp]) =>
                `<p>Character ${charId}: ${xp} XP</p>`
            ).join('') || '<p>None</p>'}
            ${lootHtml}
        `);

        currentCombatSession = null;
        document.getElementById('combatArena').style.display = 'none';
        document.getElementById('finishBtn').style.display = 'none';
        document.getElementById('processBtn').style.display = 'inline-block';
        loadCombatCharacters();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Scenarios ====================

async function loadScenarios() {
    try {
        const scenarios = await apiCall('/scenario/');
        const container = document.getElementById('scenariosList');

        if (scenarios.length === 0) {
            container.innerHTML = '<p class="placeholder">No scenarios found</p>';
            return;
        }

        container.innerHTML = scenarios.map(s => `
            <div class="list-item">
                <div class="list-item-title">${s.title}</div>
                <div class="list-item-subtitle">
                    ${s.outcomes.length} outcomes | ${s.repeatable ? 'Repeatable' : 'One-time'}
                </div>
            </div>
        `).join('');

        const select = document.getElementById('triggerScenario');
        select.innerHTML = '<option value="">-- Select Scenario --</option>' +
            scenarios.map(s => `<option value="${s.id}">${s.title}</option>`).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

document.getElementById('createScenarioForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const outcomes = [];
    document.querySelectorAll('#outcomesList .outcome-row').forEach(row => {
        const desc = row.querySelector('.outcome-desc').value;
        const type = row.querySelector('.outcome-type').value;
        const hp = row.querySelector('.outcome-hp').value;
        const weight = parseInt(row.querySelector('.outcome-weight').value);

        if (desc) {
            const outcome = {
                description: desc,
                effect_type: type,
                weight: weight,
            };
            if (hp) outcome.health_change = parseInt(hp);
            outcomes.push(outcome);
        }
    });

    try {
        const scenario = await apiCall('/scenario/', 'POST', {
            title: document.getElementById('scenarioTitle').value,
            narrative_text: document.getElementById('scenarioNarrative').value || null,
            outcomes: outcomes,
            repeatable: document.getElementById('scenarioRepeatable').checked,
        });

        showToast(`Created scenario: ${scenario.title}!`);
        e.target.reset();
        document.getElementById('outcomesList').innerHTML = `
            <div class="outcome-row">
                <input type="text" placeholder="Description" class="outcome-desc">
                <select class="outcome-type">
                    <option value="help">Help</option>
                    <option value="hurt">Hurt</option>
                    <option value="neutral">Neutral</option>
                </select>
                <input type="number" placeholder="HP change" class="outcome-hp" style="width:80px;">
                <input type="number" value="1" min="1" class="outcome-weight" style="width:60px;" title="Weight">
            </div>
        `;
        loadScenarios();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

function addOutcomeRow() {
    const container = document.getElementById('outcomesList');
    const row = document.createElement('div');
    row.className = 'outcome-row';
    row.innerHTML = `
        <input type="text" placeholder="Description" class="outcome-desc">
        <select class="outcome-type">
            <option value="help">Help</option>
            <option value="hurt">Hurt</option>
            <option value="neutral">Neutral</option>
        </select>
        <input type="number" placeholder="HP change" class="outcome-hp" style="width:80px;">
        <input type="number" value="1" min="1" class="outcome-weight" style="width:60px;" title="Weight">
    `;
    container.appendChild(row);
}

async function triggerScenario() {
    const scenarioId = document.getElementById('triggerScenario').value;
    const charId = document.getElementById('triggerCharacter').value;

    if (!scenarioId || !charId) {
        showToast('Select scenario and character', 'error');
        return;
    }

    try {
        const result = await apiCall(`/scenario/${scenarioId}/trigger/${charId}`, 'POST', {});

        const resultDiv = document.getElementById('scenarioResult');
        const effectType = result.outcome_applied.effect_type || 'neutral';

        resultDiv.className = `scenario-result ${effectType}`;
        resultDiv.innerHTML = `
            <h4>${result.narrative_text || 'Scenario Triggered!'}</h4>
            <p><strong>Outcome:</strong> ${result.outcome_applied.description}</p>
            ${result.effects_applied.health_change ? `
                <p>HP Change: ${result.effects_applied.health_change.from} → ${result.effects_applied.health_change.to}</p>
            ` : ''}
        `;

        showToast('Scenario triggered!');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function evaluateScenarios() {
    const charId = document.getElementById('evalCharacter').value;
    const triggerType = document.getElementById('evalTriggerType').value;
    const resultDiv = document.getElementById('evalResult');

    if (!charId) {
        showToast('Select a character', 'error');
        return;
    }

    try {
        const params = new URLSearchParams();
        if (triggerType) params.append('trigger_type', triggerType);

        const result = await apiCall(`/scenario/evaluate/${charId}?${params.toString()}`);

        if (result.count === 0) {
            resultDiv.innerHTML = '<p class="placeholder">No applicable scenarios found</p>';
        } else {
            resultDiv.innerHTML = `
                <h4>Found ${result.count} applicable scenario(s):</h4>
                ${result.applicable_scenarios.map(s => `
                    <div class="eval-scenario" onclick="quickTriggerScenario(${s.id}, ${charId})">
                        <strong>${s.title}</strong>
                        <div style="font-size: 0.75rem; color: var(--text-secondary);">
                            Triggers: ${s.triggers.map(t => t.type).join(', ')}
                        </div>
                    </div>
                `).join('')}
            `;
        }
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function quickTriggerScenario(scenarioId, charId) {
    try {
        const result = await apiCall(`/scenario/${scenarioId}/trigger/${charId}`, 'POST', {});
        showToast(`Triggered: ${result.outcome_applied.description}`);
        evaluateScenarios();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadScenarioHistory() {
    const charId = document.getElementById('historyCharacter').value;
    const container = document.getElementById('scenarioHistory');

    if (!charId) {
        container.innerHTML = '<p class="placeholder">Select a character</p>';
        return;
    }

    try {
        const history = await apiCall(`/scenario/history/${charId}`);

        if (history.length === 0) {
            container.innerHTML = '<p class="placeholder">No scenario history</p>';
            return;
        }

        container.innerHTML = history.map(h => `
            <div class="list-item">
                <div class="list-item-title">${h.scenario.title}</div>
                <div class="list-item-subtitle">
                    ${new Date(h.triggered_at).toLocaleString()}
                </div>
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Reference Data ====================

async function loadBaseWeapons() {
    const container = document.getElementById('baseWeaponsList');

    const params = new URLSearchParams();
    const category = document.getElementById('weaponCategory').value;
    if (category) params.append('category', category);
    const maxCost = document.getElementById('weaponMaxCost').value;
    if (maxCost) params.append('max_cost_gp', maxCost);
    const property = document.getElementById('weaponProperty').value;
    if (property) params.append('property', property);
    const search = document.getElementById('weaponSearch').value;
    if (search) params.append('search', search);

    try {
        const weapons = await apiCall(`/reference/weapons?${params.toString()}`);

        if (weapons.length === 0) {
            container.innerHTML = '<p class="placeholder">No weapons match your filters</p>';
            return;
        }

        container.innerHTML = `
            <table class="weapons-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Cost</th>
                        <th>Damage</th>
                        <th>Weight</th>
                        <th>Properties</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${weapons.map(w => `
                        <tr>
                            <td><strong>${w.name}</strong></td>
                            <td>${w.cost_display}</td>
                            <td>${w.damage_dice || '—'} ${w.damage_type ? w.damage_type[0].toUpperCase() : ''}</td>
                            <td>${w.weight} lb.</td>
                            <td class="props-cell">${formatWeaponProps(w)}</td>
                            <td>
                                <button class="btn btn-small btn-primary" onclick="createItemFromWeapon('${w.name}')">
                                    Add to DB
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

function formatWeaponProps(weapon) {
    const props = [];

    weapon.properties.forEach(p => {
        props.push(`<span class="prop-tag">${capitalize(p)}</span>`);
    });

    if (weapon.range) {
        props.push(`<span class="prop-tag range">Rg(${weapon.range})</span>`);
    }

    if (weapon.versatile_dice) {
        props.push(`<span class="prop-tag versatile">V(${weapon.versatile_dice})</span>`);
    }

    return props.join(' ') || '—';
}

async function createItemFromWeapon(weaponName) {
    try {
        const weapon = await apiCall(`/reference/weapons/${encodeURIComponent(weaponName)}`);

        const item = await apiCall('/items/', 'POST', {
            name: weapon.name,
            item_type: 'weapon',
            rarity: 'common',
            weight: weapon.weight,
            value: Math.round(weapon.cost_gp),
            description: `${capitalize(weapon.category.replace('_', ' '))} weapon. ${weapon.properties.map(capitalize).join(', ') || 'No special properties'}.`,
            properties: {
                damage_dice: weapon.damage_dice || '1d4',
                damage_type: weapon.damage_type,
                hit_bonus: 0,
                weapon_properties: weapon.properties,
                range: weapon.range || null,
                versatile_dice: weapon.versatile_dice || null,
            },
        });

        showToast(`Created ${item.name} in items database!`);
        loadItems();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadBaseArmor() {
    const container = document.getElementById('baseArmorList');

    const params = new URLSearchParams();
    const category = document.getElementById('armorCategory').value;
    if (category) params.append('category', category);
    const maxCost = document.getElementById('armorMaxCost').value;
    if (maxCost) params.append('max_cost_gp', maxCost);
    const stealthOk = document.getElementById('armorStealthOk').value;
    if (stealthOk) params.append('stealth_ok', stealthOk);
    const search = document.getElementById('armorSearch').value;
    if (search) params.append('search', search);

    try {
        const armor = await apiCall(`/reference/armor?${params.toString()}`);

        if (armor.length === 0) {
            container.innerHTML = '<p class="placeholder">No armor matches your filters</p>';
            return;
        }

        container.innerHTML = `
            <table class="weapons-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Category</th>
                        <th>Cost</th>
                        <th>AC</th>
                        <th>Weight</th>
                        <th>Stealth</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    ${armor.map(a => `
                        <tr>
                            <td><strong>${a.name}</strong></td>
                            <td>${capitalize(a.category)}</td>
                            <td>${a.cost_display}</td>
                            <td>${formatArmorAC(a)}</td>
                            <td>${a.weight} lb.</td>
                            <td>${a.stealth_disadvantage ? '<span class="prop-tag" style="background:var(--accent-danger)">Disadv.</span>' : '—'}</td>
                            <td>
                                <button class="btn btn-small btn-primary" onclick="createItemFromArmor('${a.name}')">
                                    Add to DB
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

function formatArmorAC(armor) {
    if (armor.category === 'shield') {
        return '+2';
    } else if (armor.category === 'heavy') {
        return `${armor.base_ac}`;
    } else if (armor.category === 'medium') {
        return `${armor.base_ac} + DEX (max 2)`;
    } else {
        return `${armor.base_ac} + DEX`;
    }
}

async function createItemFromArmor(armorName) {
    try {
        const armor = await apiCall(`/reference/armor/${encodeURIComponent(armorName)}`);

        let armorBonus;
        if (armor.category === 'shield') {
            armorBonus = 2;
        } else if (armor.category === 'heavy') {
            armorBonus = armor.base_ac - 10;
        } else {
            armorBonus = armor.base_ac - 10;
        }

        const item = await apiCall('/items/', 'POST', {
            name: armor.name,
            item_type: 'armor',
            rarity: 'common',
            weight: armor.weight,
            value: Math.round(armor.cost_gp),
            description: `${capitalize(armor.category)} armor.${armor.stealth_disadvantage ? ' Disadvantage on Stealth checks.' : ''}`,
            properties: {
                armor_bonus: armorBonus,
                base_ac: armor.base_ac,
                category: armor.category,
                max_dex_bonus: armor.max_dex_bonus,
                stealth_disadvantage: armor.stealth_disadvantage,
            },
        });

        showToast(`Created ${item.name} in items database!`);
        loadItems();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function loadSpells() {
    const container = document.getElementById('spellsList');

    const params = new URLSearchParams();
    const level = document.getElementById('spellLevel').value;
    if (level !== '') params.append('level', level);
    const charClass = document.getElementById('spellClass').value;
    if (charClass) params.append('class_name', charClass);
    const search = document.getElementById('spellSearch').value;
    if (search) params.append('search', search);

    try {
        const spells = await apiCall(`/reference/spells?${params.toString()}`);
        cachedSpells = spells;

        if (spells.length === 0) {
            container.innerHTML = '<p class="placeholder">No spells match your filters</p>';
            return;
        }

        container.innerHTML = spells.map(s => `
            <div class="spell-card">
                <div class="spell-card-header">
                    <span class="spell-card-name">${s.name}</span>
                    <span class="spell-card-level ${s.level === 0 ? 'cantrip' : ''}">${s.level === 0 ? 'Cantrip' : `Level ${s.level}`}</span>
                </div>
                <div class="spell-card-stats">
                    <span>Range: ${s.range} ft</span>
                    ${s.damage_dice ? `<span>Damage: ${s.damage_dice}</span>` : ''}
                    ${s.heal_dice ? `<span>Heal: ${s.heal_dice}</span>` : ''}
                </div>
                <div class="spell-card-desc">${s.description || 'No description'}</div>
                <div class="spell-card-classes">
                    ${(s.classes || []).map(c => `<span class="class-tag">${capitalize(c)}</span>`).join('')}
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

async function loadConsumables() {
    const container = document.getElementById('consumablesList');

    const params = new URLSearchParams();
    const effectType = document.getElementById('consumableType').value;
    if (effectType) params.append('effect_type', effectType);
    const search = document.getElementById('consumableSearch').value;
    if (search) params.append('search', search);

    try {
        const consumables = await apiCall(`/reference/consumables?${params.toString()}`);

        if (consumables.length === 0) {
            container.innerHTML = '<p class="placeholder">No consumables match your filters</p>';
            return;
        }

        container.innerHTML = consumables.map(c => `
            <div class="consumable-card">
                <div class="consumable-card-header">
                    <span class="consumable-card-name">${c.name}</span>
                    <span class="consumable-effect-type ${c.effect_type}">${capitalize(c.effect_type)}</span>
                </div>
                <div class="consumable-card-effect">
                    ${c.heal_amount ? `Heals ${c.heal_amount} HP` : ''}
                    ${c.damage_amount ? `Deals ${c.damage_amount} damage` : ''}
                    ${c.buff_attribute ? `+${c.buff_amount} ${c.buff_attribute} for ${c.buff_duration} turns` : ''}
                    ${c.cure_status ? `Cures ${c.cure_status}` : ''}
                </div>
                <div class="consumable-card-desc">${c.description || ''}</div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

async function loadStatusEffects() {
    const container = document.getElementById('statusEffectsList');
    const filter = document.getElementById('effectFilter').value;

    try {
        const effects = await apiCall('/reference/status-effects');
        cachedStatusEffects = effects;

        let filtered = effects;
        if (filter === 'harmful') {
            filtered = effects.filter(e => ['poisoned', 'burning', 'stunned', 'paralyzed', 'blinded', 'frightened', 'slowed', 'cursed'].includes(e.id));
        } else if (filter === 'beneficial') {
            filtered = effects.filter(e => ['hasted', 'invisible', 'blessed', 'regenerating', 'defending', 'dodging'].includes(e.id));
        }

        container.innerHTML = filtered.map(e => {
            const harmful = ['poisoned', 'burning', 'stunned', 'paralyzed', 'blinded', 'frightened', 'slowed', 'cursed'].includes(e.id);
            const beneficial = ['hasted', 'invisible', 'blessed', 'regenerating', 'defending', 'dodging'].includes(e.id);
            const type = harmful ? 'harmful' : (beneficial ? 'beneficial' : 'neutral');

            return `
                <div class="effect-item ${type}">
                    <div class="effect-item-header">
                        <span class="effect-item-name">${e.name}</span>
                        <span class="effect-item-type">${type}</span>
                    </div>
                    <div class="effect-item-desc">${e.description || 'No description'}</div>
                    <div class="effect-item-stats">
                        ${e.damage_per_turn ? `Damage/turn: ${e.damage_per_turn}` : ''}
                        ${e.modifier ? `Modifier: ${e.modifier}` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

async function loadClassAbilities() {
    const container = document.getElementById('abilitiesList');
    const classFilter = document.getElementById('abilityClassFilter').value;

    try {
        let abilities;
        if (classFilter) {
            const result = await apiCall(`/reference/abilities/class/${classFilter}`);
            abilities = result.abilities;
        } else {
            abilities = await apiCall('/reference/abilities');
        }
        cachedAbilities = abilities;

        if (abilities.length === 0) {
            container.innerHTML = '<p class="placeholder">No abilities found</p>';
            return;
        }

        container.innerHTML = abilities.map(a => `
            <div class="ability-item">
                <div class="ability-item-header">
                    <span class="ability-item-name">${a.name}</span>
                    <span class="ability-item-class">${capitalize(a.class)}</span>
                </div>
                <div class="ability-item-desc">${a.description || 'No description'}</div>
                <div class="ability-item-stats">
                    <span>Level ${a.min_level || 1}+</span>
                    ${a.max_uses ? `<span>Uses: ${a.max_uses}/${a.recovery}</span>` : ''}
                    ${a.cooldown ? `<span>CD: ${a.cooldown} turns</span>` : ''}
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

async function loadTerrainEffects() {
    const container = document.getElementById('terrainList');

    try {
        const terrain = await apiCall('/reference/terrain');

        container.innerHTML = terrain.map(t => `
            <div class="terrain-item">
                <div class="terrain-item-color" style="background: ${TERRAIN_COLORS[t.terrain_type] || '#6b7280'}"></div>
                <div class="terrain-item-info">
                    <div class="terrain-item-name">${t.name}</div>
                    <div class="terrain-item-stats">
                        <span>Move: ${t.movement_cost}</span>
                        ${t.cover_bonus > 0 ? `<span>Cover: +${t.cover_bonus} AC</span>` : ''}
                        ${t.hazardous ? `<span class="hazardous">Hazardous (${t.damage_on_enter} dmg)</span>` : ''}
                        ${!t.passable ? `<span class="impassable">Impassable</span>` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

// ==================== Monsters ====================

let cachedMonsters = [];

async function loadMonsters() {
    const container = document.getElementById('monstersList');
    const monsterType = document.getElementById('monsterType').value;
    const monsterSize = document.getElementById('monsterSize').value;
    const maxCR = document.getElementById('monsterMaxCR').value;
    const search = document.getElementById('monsterSearch').value;

    try {
        const params = new URLSearchParams();
        if (monsterType) params.append('monster_type', monsterType);
        if (monsterSize) params.append('size', monsterSize);
        if (maxCR) params.append('max_cr', maxCR);
        if (search) params.append('search', search);

        const monsters = await apiCall(`/reference/monsters?${params.toString()}`);
        cachedMonsters = monsters;

        if (monsters.length === 0) {
            container.innerHTML = '<p class="placeholder">No monsters found</p>';
            return;
        }

        container.innerHTML = monsters.map(m => `
            <div class="monster-card">
                <div class="monster-card-header">
                    <span class="monster-card-name">${m.name}</span>
                    <span class="monster-card-cr">CR ${formatCR(m.challenge_rating)}</span>
                </div>
                <div class="monster-card-type">${capitalize(m.size)} ${capitalize(m.type)}</div>
                <div class="monster-card-stats">
                    <span>HP ${m.base_hp}</span>
                    <span>AC ${m.armor_class}</span>
                    <span>XP ${m.experience_reward}</span>
                </div>
                <div class="monster-card-abilities">
                    STR ${m.strength} | DEX ${m.dexterity} | CON ${m.constitution} | INT ${m.intelligence} | WIS ${m.wisdom} | CHA ${m.charisma}
                </div>
                <div class="monster-card-desc">${m.description}</div>
                <button class="btn btn-small btn-primary" onclick="quickCreateMonster('${m.id}')" style="margin-top: 0.5rem;">Create NPC</button>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<p class="placeholder error">Error: ${e.message}</p>`;
    }
}

function formatCR(cr) {
    if (cr === 0.125) return '1/8';
    if (cr === 0.25) return '1/4';
    if (cr === 0.5) return '1/2';
    return cr.toString();
}

async function loadMonsterSelect() {
    const select = document.getElementById('monsterSelect');
    try {
        const monsters = await apiCall('/reference/monsters');
        cachedMonsters = monsters;

        // Sort by CR then name
        monsters.sort((a, b) => a.challenge_rating - b.challenge_rating || a.name.localeCompare(b.name));

        select.innerHTML = '<option value="">-- Select Monster --</option>' +
            monsters.map(m => `<option value="${m.id}">${m.name} (CR ${formatCR(m.challenge_rating)})</option>`).join('');

        // Add change handler to show preview
        select.onchange = () => {
            const monsterId = select.value;
            const preview = document.getElementById('monsterPreview');
            if (monsterId) {
                const monster = cachedMonsters.find(m => m.id === monsterId);
                if (monster) {
                    preview.style.display = 'block';
                    preview.querySelector('.monster-stats').innerHTML = `
                        <div><strong>${monster.name}</strong> - ${capitalize(monster.size)} ${capitalize(monster.type)}</div>
                        <div>CR ${formatCR(monster.challenge_rating)} | HP ${monster.base_hp} | AC ${monster.armor_class}</div>
                        <div>STR ${monster.strength} | DEX ${monster.dexterity} | CON ${monster.constitution}</div>
                        <div>INT ${monster.intelligence} | WIS ${monster.wisdom} | CHA ${monster.charisma}</div>
                    `;
                }
            } else {
                preview.style.display = 'none';
            }
        };
    } catch (e) {
        console.error('Failed to load monster select:', e);
    }
}

async function createMonster() {
    const monsterId = document.getElementById('monsterSelect').value;
    const customName = document.getElementById('monsterName').value;

    if (!monsterId) {
        showToast('Select a monster template', 'error');
        return;
    }

    try {
        const params = new URLSearchParams();
        if (customName) params.append('name', customName);

        const character = await apiCall(`/character/from-monster/${monsterId}?${params.toString()}`, 'POST');
        showToast(`Created ${character.name}!`);

        document.getElementById('monsterName').value = '';
        loadCharacters();
        populateCharacterSelects();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function quickCreateMonster(monsterId) {
    try {
        const character = await apiCall(`/character/from-monster/${monsterId}`, 'POST');
        showToast(`Created ${character.name}!`);
        loadCharacters();
        populateCharacterSelects();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ==================== Events ====================

async function loadEvents() {
    try {
        const eventType = document.getElementById('filterEventType').value;
        const charId = document.getElementById('filterEventCharacter').value;

        const query = {};
        if (eventType) query.event_type = eventType;
        if (charId) query.character_id = parseInt(charId);
        query.limit = 50;

        const events = await apiCall('/events/query', 'POST', query);
        const container = document.getElementById('eventsList');

        if (events.length === 0) {
            container.innerHTML = '<p class="placeholder">No events found</p>';
            return;
        }

        container.innerHTML = events.map(e => `
            <div class="event-item">
                <span class="event-type">${e.event_type}</span>
                <span class="event-time">${new Date(e.timestamp).toLocaleString()}</span>
                <div class="event-desc">
                    ${e.description || `Character: ${e.character_id || 'N/A'}`}
                </div>
            </div>
        `).join('');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

document.getElementById('logEventForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    try {
        const charId = document.getElementById('eventCharacter').value;

        await apiCall('/events/', 'POST', {
            event_type: document.getElementById('eventType').value,
            character_id: charId ? parseInt(charId) : null,
            description: document.getElementById('eventDescription').value || null,
        });

        showToast('Event logged!');
        e.target.reset();
        loadEvents();
    } catch (e) {
        showToast(e.message, 'error');
    }
});

// ==================== Admin Panel ====================

function setAdminXp(amount) {
    document.getElementById('adminXpAmount').value = amount;
}

async function addExperience() {
    const charId = document.getElementById('adminCharSelect').value;
    const amount = parseInt(document.getElementById('adminXpAmount').value);

    if (!charId) {
        showToast('Select a character', 'error');
        return;
    }

    try {
        const result = await apiCall(`/character/${charId}/experience?amount=${amount}`, 'POST');
        showToast(`Added ${amount} XP! Total: ${result.new_experience}`);

        // Refresh character display if this is the selected character
        if (selectedCharacter?.id === parseInt(charId)) {
            selectCharacter(parseInt(charId));
        }
        loadCharacters();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function addGold() {
    const charId = document.getElementById('adminCharSelect').value;
    const amount = parseInt(document.getElementById('adminGoldAmount').value);

    if (!charId) {
        showToast('Select a character', 'error');
        return;
    }

    try {
        const result = await apiCall(`/character/${charId}/gold?amount=${amount}`, 'POST');
        showToast(`Added ${amount} gold! Total: ${result.new_gold}`);

        // Refresh character display if this is the selected character
        if (selectedCharacter?.id === parseInt(charId)) {
            selectCharacter(parseInt(charId));
        }
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function resetDatabase() {
    if (!confirm('Are you sure you want to RESET THE ENTIRE DATABASE? This cannot be undone!')) return;
    if (!confirm('This will delete ALL characters, items, quests, zones, combat data, and reset all IDs to 1. Are you REALLY sure?')) return;

    try {
        const result = await apiCall('/admin/reset', 'POST');
        console.log('Reset result:', result);
        showToast('Database reset complete! All IDs reset to 1.');

        // Clear UI state
        selectedCharacter = null;
        document.getElementById('characterDetails').innerHTML = '<p class="placeholder">Select a character to view details</p>';

        // Refresh all data
        loadCharacters();
        populateCharacterSelects();
        loadItems();
        loadZones();
        loadQuests();
    } catch (e) {
        showToast('Reset failed: ' + e.message, 'error');
    }
}

// ==================== Helpers ====================

async function populateCharacterSelects() {
    try {
        const characters = await apiCall('/character/');

        const selects = [
            'invCharSelect', 'moveCharSelect', 'questCharSelect',
            'triggerCharacter', 'historyCharacter', 'eventCharacter',
            'filterEventCharacter', 'evalCharacter', 'adminCharSelect'
        ];

        selects.forEach(id => {
            const select = document.getElementById(id);
            if (select) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">-- Select Character --</option>' +
                    characters.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
                if (currentVal) select.value = currentVal;
            }
        });
    } catch (e) {
        console.error('Failed to populate character selects:', e);
    }
}

// ==================== Initialization ====================

async function init() {
    await checkConnection();
    loadTabData('characters');

    setInterval(checkConnection, 30000);
}

init();
