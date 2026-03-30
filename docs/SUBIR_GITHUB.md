# 📤 Guía para Subir a GitHub

## Paso 1: Inicializar Repositorio Git

Abre una terminal en la carpeta del proyecto:

```bash
cd C:\Users\hp\MisProyectos\isosmart-titanium
git init
```

## Paso 2: Agregar Archivos

```bash
git add .
```

## Paso 3: Crear Primer Commit

```bash
git commit -m "Initial commit: IsoSmart Titanium v4.0

- Aplicacion Streamlit con visor BIM 3D
- Motor de presupuestos para Isotex e ICF
- Asistente IA con Google Gemini
- Generacion de PDF y Excel
- Calculculos estructurales avanzados
- Gestion de proyectos"
```

## Paso 4: Conectar con GitHub

Tu repositorio en GitHub ya esta creado: `https://github.com/jukaben32/isosmart-titanium`

Conecta tu repositorio local:

```bash
git branch -M main
git remote add origin https://github.com/jukaben32/isosmart-titanium.git
```

## Paso 5: Subir a GitHub

```bash
git push -u origin main
```

Si te pide credenciales:
- Usa tu username: `jukaben32`
- Usa un **Personal Access Token** (no tu contrasena)
  - Crea uno en: https://github.com/settings/tokens
  - Marca los permisos: `repo`, `workflow`

## Verificar Subida

1. Ve a https://github.com/jukaben32/isosmart-titanium
2. Refresca la pagina
3. Deberias ver todos los archivos

## Comandos Utiles

### Ver estado:
```bash
git status
```

### Ver historial:
```bash
git log --oneline
```

### Actualizar despues de cambios:
```bash
git add .
git commit -m "Descripcion de cambios"
git push
```

### Descargar actualizaciones:
```bash
git pull origin main
```

## Solucion de Problemas

### Error: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/jukaben32/isosmart-titanium.git
```

### Error: "Updates were rejected"
```bash
git pull origin main --rebase
git push
```

### Error de autenticacion:
Usa HTTPS con token:
```bash
git remote set-url origin https://TU_TOKEN@github.com/jukaben32/isosmart-titanium.git
git push
```

---

**Listo!** Tu proyecto ahora esta en GitHub
