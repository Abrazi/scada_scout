# 🎨 SCADA Scout - Epic Dark & Bright Themes

## Visual Comparison Guide

### Epic Dark Theme 🌙
**Optimized for 24/7 Control Room Operation**

```
┌────────────────────────────────────────────────────────────┐
│ File  View  Tools  Help                      [Scada Scout] │
├────────────────────────────────────────────────────────────┤
│ ■ ▶ ◼ ⟳  [Search...]                                       │
├─────────────┬──────────────────────────────────────────────┤
│             │                                                │
│ Device Tree │  Signal View                                  │
│             │                                                │
│ ● IED-1     │  Name        Value     Quality   Time         │
│   Connected │  ──────────────────────────────────────────   │
│             │  Voltage     230.5V    GOOD      10:23:45    │
│ ● IED-2     │  Current     15.2A     GOOD      10:23:45    │
│   Connected │  Frequency   50.01Hz   GOOD      10:23:45    │
│             │  Power       3.5kW     GOOD      10:23:45    │
│             │                                                │
│             │  ⚠ ALARM: Critical - Overvoltage              │
│             │                                                │
├─────────────┴──────────────────────────────────────────────┤
│ Status: Ready | Devices: 2 Connected | Updates: Active     │
└────────────────────────────────────────────────────────────┘

COLOR SCHEME:
Background:    #0D1117 (Deep Space)
Surface:       #161B22 (Elevated)
Text:          #E6EDF3 (Near White)
Primary:       #00D9FF (Electric Cyan) ◀ Accents
Success:       #39FF14 (Neon Green)   ● Connected
Warning:       #FFB300 (Amber)        ⚠ Warning
Critical:      #FF1744 (Crimson)      ⚠ CRITICAL
```

**Best For:**
- 🌙 Nighttime operation
- 🖥️ Control room environments
- 👁️ Reduced eye strain
- 🔋 OLED displays (power saving)
- 📊 Focus on critical data

---

### Epic Bright Theme ☀️
**Optimized for Daylight Operation**

```
┌────────────────────────────────────────────────────────────┐
│ File  View  Tools  Help                      [Scada Scout] │
├────────────────────────────────────────────────────────────┤
│ ■ ▶ ◼ ⟳  [Search...]                                       │
├─────────────┬──────────────────────────────────────────────┤
│             │                                                │
│ Device Tree │  Signal View                                  │
│             │                                                │
│ ● IED-1     │  Name        Value     Quality   Time         │
│   Connected │  ──────────────────────────────────────────   │
│             │  Voltage     230.5V    GOOD      10:23:45    │
│ ● IED-2     │  Current     15.2A     GOOD      10:23:45    │
│   Connected │  Frequency   50.01Hz   GOOD      10:23:45    │
│             │  Power       3.5kW     GOOD      10:23:45    │
│             │                                                │
│             │  ⚠ ALARM: Critical - Overvoltage              │
│             │                                                │
├─────────────┴──────────────────────────────────────────────┤
│ Status: Ready | Devices: 2 Connected | Updates: Active     │
└────────────────────────────────────────────────────────────┘

COLOR SCHEME:
Background:    #F6F8FA (Soft White)
Surface:       #FFFFFF (Pure White)
Text:          #24292F (Near Black)
Primary:       #0969DA (Professional Blue) ◀ Accents
Success:       #1A7F37 (Forest Green)      ● Connected
Warning:       #9A6700 (Dark Amber)        ⚠ Warning
Critical:      #CF222E (Bright Red)        ⚠ CRITICAL
```

**Best For:**
- ☀️ Daytime operation
- 🏢 Well-lit environments
- 📱 Mobile/tablet use
- 🖨️ Print-friendly
- 👥 Public displays

---

## Quick Comparison

| Feature              | Epic Dark 🌙       | Epic Bright ☀️     |
|---------------------|--------------------|--------------------|
| Background          | Deep (#0D1117)     | Soft White (#F6F8FA)|
| Primary Accent      | Cyan (#00D9FF)     | Blue (#0969DA)     |
| Success/Connected   | Neon Green         | Forest Green       |
| Critical Alarm      | Crimson Red        | Bright Red         |
| Eye Strain          | ⭐⭐⭐⭐⭐ Very Low | ⭐⭐⭐ Moderate    |
| Contrast Ratio      | 15:1               | 12:1               |
| Best Lighting       | Dim/Dark           | Bright/Daylight    |
| Power Consumption   | Lower (OLED)       | Higher             |

---

## How to Switch

### Via Menu:
```
View → Theme → Epic Dark
View → Theme → Epic Bright
View → Theme → Toggle Theme
```

### Via Keyboard:
```
Press: Ctrl + Shift + T
```

### Programmatically:
```python
from src.ui.theme_manager import get_theme_manager
from src.ui.theme_presets import ThemeType

theme = get_theme_manager()
theme.set_theme(ThemeType.DARK)   # or ThemeType.BRIGHT
```

---

## Status Colors (Both Themes)

### Device Status:
```
● Green  = Connected
● Red    = Disconnected
● Blue   = Connecting
● Orange = Error
```

### Signal Quality:
```
● Green  = Good
● Red    = Bad
● Yellow = Questionable
● Gray   = Not Connected
```

### Alarm Severity:
```
⚠ Red    = Critical (Flashing)
⚠ Orange = High Priority
⚠ Amber  = Medium Priority
⚠ Yellow = Low Priority
⚠ Gray   = Acknowledged
```

---

## Accessibility Features ♿

✅ **High Contrast**
- 4.5:1 minimum for text
- 7:1 for alarm colors
- WCAG AA compliant

✅ **Focus Indicators**
- 3px visible outline
- Color-independent
- Keyboard navigation support

✅ **Touch-Friendly**
- 44px minimum target size
- Adequate spacing
- Tablet optimized

✅ **Disabled States**
- 40% opacity
- Grayed out appearance
- Clear visual indication

---

## Theme Persistence 💾

Your theme choice is **automatically saved** and will be restored when you restart the application. No configuration needed!

Settings stored in: `~/.config/scada_scout/application.ini`

---

## Design Philosophy

### Epic Dark 🌙
- Inspired by: Modern code editors, control room displays
- Psychology: Reduces eye fatigue, improves focus
- Color theory: Blue undertones for comfort, neon accents for alerts
- Use case: Long-duration monitoring, critical operations

### Epic Bright ☀️
- Inspired by: Professional dashboards, industrial HMIs
- Psychology: Clean, professional, trustworthy
- Color theory: Warm undertones, clear hierarchy
- Use case: Field operations, well-lit environments

---

**Enjoy the new theme system!** 🎉

For more details, see: `THEME_SYSTEM_GUIDE.md`
