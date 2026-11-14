# IOFlow Frontend Theming Guide

## Overview

IOFlow uses a centralized theming system with CSS variables defined in `src/index.css` and Tailwind configuration in `tailwind.config.js`. This allows changing brand colors from a single location.

## Color System

### CSS Variables (defined in `src/index.css`)

```css
:root {
  /* Primary Colors - Cyan/Teal */
  --color-primary: #00A0D4;
  --color-primary-light: #33B3DD;
  --color-primary-dark: #0080AA;
  --color-primary-darker: #006080;

  /* Secondary Colors - Teal/Green */
  --color-secondary: #00B4A1;
  --color-secondary-light: #33C3B4;
  --color-secondary-dark: #009080;

  /* Accent Colors - Coral/Orange (for CTAs) */
  --color-accent: #e9798c;
  --color-accent-end: #f9a06a;

  /* Gradients */
  --gradient-primary: linear-gradient(to right, var(--color-primary), var(--color-secondary));
  --gradient-accent: linear-gradient(to right, var(--color-accent), var(--color-accent-end));
}
```

## Available CSS Classes

### Buttons

| Class | Usage |
|-------|-------|
| `btn-primary` | Primary action buttons (gradient) |
| `btn-accent` | Call-to-action buttons like Import, Install |
| `btn-secondary` | Secondary/outline buttons |

Example:
```jsx
<button className="btn-primary">Save Changes</button>
<button className="btn-accent">Import</button>
<button className="btn-secondary">Cancel</button>
```

### Form Inputs

| Class | Usage |
|-------|-------|
| `input-primary` | Text inputs with primary focus color |
| `select-primary` | Select dropdowns with primary focus color |
| `checkbox-primary` | Checkboxes with primary color |

Example:
```jsx
<input type="text" className="input-primary" />
<select className="select-primary">...</select>
<input type="checkbox" className="checkbox-primary" />
```

### Toggle Switches

```jsx
<button className={`toggle-primary ${isActive ? 'active' : 'inactive'}`}>
  <span className={isActive ? 'translate-x-5' : 'translate-x-0'} />
</button>
```

### Tabs

```jsx
<button className={`tab-primary ${isActive ? 'active' : 'inactive'}`}>
  Tab Name
</button>
```

### Links

```jsx
<a className="link-primary" href="...">Link Text</a>
```

### Badges

```jsx
<span className="badge-primary">Primary Badge</span>
<span className="badge-secondary">Secondary Badge</span>
```

### Loading Spinners

```jsx
<div className="spinner-primary h-12 w-12" />
```

### Info Boxes

```jsx
<div className="info-box-primary">
  <p>Information message</p>
</div>
```

## Tailwind Utility Classes

### Background Colors

| Class | Description |
|-------|-------------|
| `bg-primary` | Primary solid color |
| `bg-primary-10` | Primary at 10% opacity |
| `bg-primary-20` | Primary at 20% opacity |
| `bg-secondary` | Secondary solid color |
| `bg-accent` | Accent solid color |
| `bg-gradient-primary` | Primary gradient |
| `bg-gradient-accent` | Accent gradient |

### Text Colors

| Class | Description |
|-------|-------------|
| `text-primary` | Primary text color |
| `text-primary-dark` | Darker primary text |
| `text-secondary` | Secondary text color |
| `text-accent` | Accent text color |

### Border Colors

| Class | Description |
|-------|-------------|
| `border-primary` | Primary border |
| `border-primary-30` | Primary at 30% opacity |
| `border-secondary` | Secondary border |
| `border-accent` | Accent border |

### Focus States

| Class | Description |
|-------|-------------|
| `focus:ring-primary` | Primary focus ring |
| `focus:border-primary` | Primary focus border |
| `ring-theme-primary` | Theme primary ring |

## Migration Guide

### Before (Hardcoded Colors)

```jsx
// ❌ Don't use hardcoded hex values
<button className="bg-gradient-to-r from-[#00A0D4] to-[#00B4A1] hover:shadow-lg text-white">
  Save
</button>

<input className="focus:ring-[#00A0D4] focus:border-[#00A0D4]" />

<span className="text-[#00A0D4]">Link</span>

<div className="bg-[#00A0D4]/10 border-[#00A0D4]/30">Info</div>
```

### After (Theme Classes)

```jsx
// ✅ Use theme classes
<button className="btn-primary">Save</button>

<input className="input-primary" />

<span className="text-primary">Link</span>

<div className="info-box-primary">Info</div>
```

## Common Replacements

| Hardcoded | Replacement |
|-----------|-------------|
| `bg-gradient-to-r from-[#00A0D4] to-[#00B4A1]` | `btn-primary` or `bg-gradient-primary` |
| `bg-gradient-to-r from-[#e9798c] to-[#f9a06a]` | `btn-accent` or `bg-gradient-accent` |
| `text-[#00A0D4]` | `text-primary` |
| `text-[#0080AA]` | `text-primary-dark` |
| `text-[#00B4A1]` | `text-secondary` |
| `bg-[#00A0D4]` | `bg-primary` |
| `bg-[#00A0D4]/10` | `bg-primary-10` |
| `border-[#00A0D4]` | `border-primary` |
| `border-[#00A0D4]/30` | `border-primary-30` |
| `focus:ring-[#00A0D4]` | `focus:ring-primary` |
| `focus:border-[#00A0D4]` | `focus:border-primary` |
| `hover:text-[#0080AA]` | `hover:text-primary-dark` |

## Changing Brand Colors

To change the brand colors globally, edit the CSS variables in `src/index.css`:

```css
:root {
  --color-primary: #YOUR_NEW_PRIMARY;
  --color-primary-light: #YOUR_LIGHTER_SHADE;
  --color-primary-dark: #YOUR_DARKER_SHADE;
  /* ... */
}
```

All components using theme classes will automatically update.

## Files Still Using Hardcoded Colors

The following files still contain hardcoded color values that should be migrated:

- `src/components/applications/*.js` (modals)
- `src/pages/*.js` (various pages)
- `src/components/marketplace/*.js`
- `src/pages/LandingPage/components/*.js`

Priority for migration:
1. Shared components (used across multiple pages)
2. High-traffic pages (Dashboard, Flows, Applications)
3. Admin pages
4. Landing page components
