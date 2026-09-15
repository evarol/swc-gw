(function () {
  'use strict';

  /** Shared-index 3D view. Coordinates receive one common scale in both layouts. */
  window.createMotorSpatial = function (options) {
    const { container, trees, coupling, onSelect } = options;
    let colors = options.colors;
    if (!window.THREE || !THREE.OrbitControls) throw new Error('The 3D renderer has not loaded.');
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(colors.background);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    const canvas = renderer.domElement;
    canvas.style.cssText = 'display:block;width:100%;height:100%;touch-action:none;outline-offset:-3px;';
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Interactive 3D motor neuron trees and Gromov–Wasserstein transport connectors. Drag to rotate; scroll or pinch to zoom; hover a node or connector to highlight the linked matrices. Click to pin a selection.');
    container.style.position = 'relative';
    container.appendChild(canvas);

    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 3000);
    const controls = new THREE.OrbitControls(camera, canvas);
    canvas.removeAttribute('tabindex');
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.enablePan = true;
    controls.minDistance = 20;
    controls.maxDistance = 900;
    controls.autoRotate = false;

    const rawBounds = trees.map(tree => new THREE.Box3().setFromPoints(tree.nodes.map(n => new THREE.Vector3(n.x, n.y, n.z))));
    const rawCenters = rawBounds.map(bounds => bounds.getCenter(new THREE.Vector3()));
    const rawSizes = rawBounds.map(bounds => bounds.getSize(new THREE.Vector3()));
    const commonExtent = Math.max(...rawSizes.flatMap(size => [size.x, size.y, size.z]), 1e-9);
    const scale = 120 / commonExtent;
    const sharedCenter = rawBounds[0].clone().union(rawBounds[1]).getCenter(new THREE.Vector3());
    const separation = Math.max(62, (rawSizes[0].x + rawSizes[1].x) * scale / 4 + 23);
    const pointPositions = [[], []];
    const edgeViews = [];
    const nodeViews = [];
    const resources = [];
    const sphere = new THREE.SphereGeometry(1, 10, 7);
    resources.push(sphere);
    const matrix = new THREE.Matrix4();
    const rotation = new THREE.Quaternion();
    const triadRotation = new THREE.Quaternion();
    const focusColor = new THREE.Color(colors.focus);
    const mismatchColor = new THREE.Color(colors.wrong || colors.foreground);
    const treeColors = [new THREE.Color(colors.a), new THREE.Color(colors.b)];
    let selection = null;
    let layout = 'separated';
    let connectorsVisible = true;
    let disposed = false;
    let animationFrame;
    let lastHoverKey = '';
    let dragStart = null;
    let dragged = false;
    let width = 1;
    let height = 1;

    const labels = trees.map(tree => {
      const label = document.createElement('div');
      label.textContent = tree.label;
      label.className = 'text-small';
      label.style.cssText = 'position:absolute;pointer-events:none;transform:translate(-50%,-50%);font-weight:500;white-space:nowrap;';
      label.style.color = colors.foreground;
      container.appendChild(label);
      return label;
    });

    trees.forEach((tree, treeIndex) => {
      const nodeMaterial = new THREE.MeshBasicMaterial({ color: colors.foreground });
      const nodes = new THREE.InstancedMesh(sphere, nodeMaterial, tree.nodes.length);
      nodes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      nodes.userData.treeIndex = treeIndex;
      nodes.frustumCulled = false;
      // Instance colors carry the tree and selected colors without changing object count.
      nodeMaterial.color.setRGB(1, 1, 1); // Neutral multiplier; all displayed colors come from instance colors.
      for (let i = 0; i < tree.nodes.length; i++) nodes.setColorAt(i, treeColors[treeIndex]);
      nodeViews.push(nodes);
      scene.add(nodes);
      const edgeGeometry = new THREE.BufferGeometry();
      edgeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(tree.edges.length * 6), 3));
      const edgeMaterial = new THREE.LineBasicMaterial({ color: treeColors[treeIndex], transparent: true, opacity: 0.78 });
      const edges = new THREE.LineSegments(edgeGeometry, edgeMaterial);
      edges.frustumCulled = false;
      scene.add(edges);
      edgeViews.push(edges);
      resources.push(nodeMaterial, edgeGeometry, edgeMaterial);
    });

    // Each segment has its own alpha. A single draw call preserves every positive coupling.
    const transportGeometry = new THREE.BufferGeometry();
    transportGeometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(coupling.length * 6), 3));
    transportGeometry.setAttribute('rgba', new THREE.Float32BufferAttribute(new Float32Array(coupling.length * 8), 4));
    const transportMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      vertexShader: 'attribute vec4 rgba; varying vec4 vRGBA; void main(){vRGBA=rgba;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader: 'varying vec4 vRGBA; void main(){gl_FragColor=vRGBA;}',
    });
    const transport = new THREE.LineSegments(transportGeometry, transportMaterial);
    transport.frustumCulled = false;
    transport.renderOrder = 1;
    scene.add(transport);
    resources.push(transportGeometry, transportMaterial);
    const maxMass = Math.max(...coupling.map(link => link.mass), 1e-12);

    // A camera-relative orientation widget uses the supplied palette only.
    const triad = document.createElement('div');
    triad.style.cssText = 'position:absolute;left:10px;bottom:10px;width:70px;height:70px;pointer-events:none;';
    triad.setAttribute('aria-hidden', 'true');
    const axisEls = ['X', 'Y', 'Z'].map((name, axisIndex) => {
      const el = document.createElement('div');
      el.style.cssText = 'position:absolute;left:35px;top:35px;transform-origin:0 50%;height:1px;';
      el.style.background = [colors.a, colors.b, colors.foreground][axisIndex];
      const caption = document.createElement('span');
      caption.textContent = name;
      caption.className = 'text-small';
      caption.style.cssText = 'position:absolute;left:100%;top:0;font-weight:500;padding-left:3px;';
      caption.style.color = colors.foreground;
      el.appendChild(caption);
      triad.appendChild(el);
      return { el, caption };
    });
    container.appendChild(triad);
    const axes = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)];
    const projected = new THREE.Vector3();

    function setColors(next) {
      colors = Object.assign({}, colors, next);
      scene.background.set(colors.background);
      focusColor.set(colors.focus);
      mismatchColor.set(colors.wrong || colors.foreground);
      treeColors[0].set(colors.a);
      treeColors[1].set(colors.b);
      edgeViews.forEach((edges, index) => edges.material.color.copy(treeColors[index]));
      labels.forEach(label => { label.style.color = colors.foreground; });
      axisEls.forEach((axis, index) => {
        axis.el.style.background = [colors.a, colors.b, colors.foreground][index];
        axis.caption.style.color = colors.foreground;
      });
      repaintSelection();
    }

    function repaintSelection() {
      const selected = [new Set(selection && selection.a || []), new Set(selection && selection.b || [])];
      const active = selected[0].size + selected[1].size > 0;
      trees.forEach((tree, treeIndex) => {
        tree.nodes.forEach((node, index) => {
          const isSelected = selected[treeIndex].has(index);
          const radius = (node.parent < 0 ? 0.85 : 0.50) * (isSelected ? 2.65 : 1);
          matrix.compose(pointPositions[treeIndex][index], rotation, new THREE.Vector3(radius, radius, radius));
          nodeViews[treeIndex].setMatrixAt(index, matrix);
          nodeViews[treeIndex].setColorAt(index, isSelected ? focusColor : treeColors[treeIndex]);
        });
        nodeViews[treeIndex].instanceMatrix.needsUpdate = true;
        nodeViews[treeIndex].instanceColor.needsUpdate = true;
      });
      const rgba = transportGeometry.attributes.rgba;
      coupling.forEach((link, index) => {
        const exact = selection && selection.pair && selection.pair[0] === link.i && selection.pair[1] === link.j;
        const incident = selected[0].has(link.i) || selected[1].has(link.j);
        const weight = Math.sqrt(Math.max(0, link.mass) / maxMass);
        const alpha = exact ? 1 : incident ? 0.45 + weight * 0.45 : active ? 0.018 : link.correct===false ? .5 : 0.035 + weight * 0.18;
        const first = incident ? focusColor : link.correct===false ? mismatchColor : treeColors[0];
        const second = incident ? focusColor : link.correct===false ? mismatchColor : treeColors[1];
        rgba.setXYZW(index * 2, first.r, first.g, first.b, alpha);
        rgba.setXYZW(index * 2 + 1, second.r, second.g, second.b, alpha);
      });
      rgba.needsUpdate = true;
    }

    function setLayout(mode) {
      layout = mode === 'native' ? 'native' : 'separated';
      trees.forEach((tree, treeIndex) => {
        const center = layout === 'native' ? sharedCenter : rawCenters[treeIndex];
        pointPositions[treeIndex] = tree.nodes.map(node => new THREE.Vector3(node.x, node.y, node.z)
          .sub(center).multiplyScalar(scale).add(new THREE.Vector3(layout === 'separated' ? (treeIndex ? separation : -separation) : 0, 0, 0)));
        const positions = edgeViews[treeIndex].geometry.attributes.position;
        tree.edges.forEach((edge, index) => {
          positions.setXYZ(index * 2, ...pointPositions[treeIndex][edge[0]].toArray());
          positions.setXYZ(index * 2 + 1, ...pointPositions[treeIndex][edge[1]].toArray());
        });
        positions.needsUpdate = true;
        edgeViews[treeIndex].geometry.computeBoundingSphere();
      });
      const positions = transportGeometry.attributes.position;
      coupling.forEach((link, index) => {
        positions.setXYZ(index * 2, ...pointPositions[0][link.i].toArray());
        positions.setXYZ(index * 2 + 1, ...pointPositions[1][link.j].toArray());
      });
      positions.needsUpdate = true;
      transportGeometry.computeBoundingSphere();
      repaintSelection();
      fitCamera();
    }

    function fitCamera() {
      const bounds = new THREE.Box3().setFromPoints(pointPositions.flat());
      const size = bounds.getSize(new THREE.Vector3());
      const center = bounds.getCenter(new THREE.Vector3());
      const fov = THREE.MathUtils.degToRad(camera.fov);
      const distance = Math.max(size.y, size.x / Math.max(camera.aspect, 0.4), size.z) / (2 * Math.tan(fov / 2)) * 1.25;
      camera.position.set(center.x + distance * 0.045, center.y + distance * 0.035, center.z + distance);
      controls.target.copy(center);
      camera.lookAt(center);
      controls.update();
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    function projectPosition(position) {
      camera.updateMatrixWorld();
      const bounds = canvas.getBoundingClientRect();
      const p = position.clone().project(camera);
      const localX = (p.x + 1) * bounds.width / 2;
      const localY = (1 - p.y) * bounds.height / 2;
      return { x: bounds.left + localX, y: bounds.top + localY, localX, localY, visible: p.z >= -1 && p.z <= 1 && Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1 };
    }
    function projectNode(treeIndex, nodeIndex) {
      const position = pointPositions[treeIndex] && pointPositions[treeIndex][nodeIndex];
      return position ? projectPosition(position) : null;
    }
    function projectConnector(index, fraction = 0.5) {
      const link = coupling[index];
      return link ? Object.assign(projectPosition(pointPositions[0][link.i].clone().lerp(pointPositions[1][link.j], fraction)), { i: link.i, j: link.j, mass: link.mass }) : null;
    }
    function distanceToConnector(event, index) {
      const link = coupling[index];
      const a = projectNode(0, link.i);
      const b = projectNode(1, link.j);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const denominator = dx * dx + dy * dy;
      const t = denominator ? Math.max(0, Math.min(1, ((event.clientX - a.x) * dx + (event.clientY - a.y) * dy) / denominator)) : 0;
      return Math.pow(event.clientX - a.x - t * dx, 2) + Math.pow(event.clientY - a.y - t * dy, 2);
    }
    function pick(event) {
      const bounds = canvas.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) return null;
      pointer.set((event.clientX - bounds.left) / bounds.width * 2 - 1, -(event.clientY - bounds.top) / bounds.height * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      raycaster.params.Line.threshold = Math.max(0.28, camera.position.distanceTo(controls.target) / Math.max(height, 1) * 0.8);
      const hits = raycaster.intersectObjects(nodeViews, false);
      if (hits.length) {
        const hit = hits[0];
        const treeIndex = hit.object.userData.treeIndex;
        return { a: treeIndex === 0 ? [hit.instanceId] : [], b: treeIndex === 1 ? [hit.instanceId] : [], source: 'spatial' };
      }
      if (connectorsVisible) {
        const lines = raycaster.intersectObject(transport, false);
        if (lines.length) {
          // At crossings choose the segment closest to the pointer, then the nearer segment.
          lines.forEach(hit => { hit.screenDistance = distanceToConnector(event, Math.floor(hit.index / 2)); });
          lines.sort((a, b) => a.screenDistance - b.screenDistance || a.distance - b.distance);
          const link = coupling[Math.floor(lines[0].index / 2)];
          if (link) return { a: [link.i], b: [link.j], pair: [link.i, link.j], source: 'spatial' };
        }
      }
      return null;
    }

    function emitHover(value) {
      const key = value ? JSON.stringify([value.a, value.b, value.pair]) : '';
      canvas.style.cursor = value ? 'pointer' : 'grab';
      if (key !== lastHoverKey) {
        lastHoverKey = key;
        onSelect(value);
      }
    }
    function onPointerDown(event) {
      dragStart = { x: event.clientX, y: event.clientY };
      dragged = false;
      canvas.style.cursor = 'grabbing';
    }
    function onPointerMove(event) {
      if (dragStart) {
        if (Math.hypot(event.clientX - dragStart.x, event.clientY - dragStart.y) > 4) dragged = true;
        return;
      }
      emitHover(pick(event));
    }
    function onPointerUp(event) {
      const wasClick = dragStart && !dragged;
      dragStart = null;
      if (wasClick) {
        const value = pick(event);
        if (value) onSelect(Object.assign(value, { pin: true }));
        else onSelect(null);
      }
      canvas.style.cursor = 'grab';
    }
    function onPointerLeave() {
      if (!dragStart) emitHover(null);
    }
    function onPointerCancel() {
      dragStart = null;
      dragged = false;
      emitHover(null);
    }
    function onKeyDown(event) {
      const offset = camera.position.clone().sub(controls.target);
      const spherical = new THREE.Spherical().setFromVector3(offset);
      let handled = true;
      if (event.key === 'ArrowLeft') spherical.theta -= 0.1;
      else if (event.key === 'ArrowRight') spherical.theta += 0.1;
      else if (event.key === 'ArrowUp') spherical.phi -= 0.1;
      else if (event.key === 'ArrowDown') spherical.phi += 0.1;
      else if (event.key === '+' || event.key === '=') spherical.radius *= 0.9;
      else if (event.key === '-') spherical.radius *= 1.1;
      else if (event.key === 'Escape') onSelect(null);
      else handled = false;
      if (handled) {
        event.preventDefault();
        spherical.makeSafe();
        spherical.radius = Math.max(controls.minDistance, Math.min(controls.maxDistance, spherical.radius));
        camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
        controls.update();
      }
    }
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerleave', onPointerLeave);
    canvas.addEventListener('pointercancel', onPointerCancel);
    window.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('keydown', onKeyDown);

    function resize() {
      const bounds = container.getBoundingClientRect();
      const previousAspect = camera.aspect;
      width = Math.max(1, Math.floor(bounds.width));
      height = Math.max(1, Math.floor(bounds.height));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (pointPositions[0].length && Math.abs(previousAspect - camera.aspect) > 0.25) fitCamera();
    }
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);

    function animate() {
      if (disposed) return;
      animationFrame = requestAnimationFrame(animate);
      controls.update();
      trees.forEach((tree, treeIndex) => {
        const bounds = new THREE.Box3().setFromPoints(pointPositions[treeIndex]);
        bounds.getCenter(projected);
        projected.y = bounds.max.y + 5;
        projected.project(camera);
        labels[treeIndex].style.left = ((projected.x + 1) / 2 * width) + 'px';
        labels[treeIndex].style.top = ((1 - projected.y) / 2 * height) + 'px';
        labels[treeIndex].style.display = projected.z > 1 || Math.abs(projected.x) > 1.15 || Math.abs(projected.y) > 1.15 ? 'none' : '';
      });
      triadRotation.copy(camera.quaternion).invert();
      axes.forEach((axis, index) => {
        projected.copy(axis).applyQuaternion(triadRotation);
        const angle = Math.atan2(-projected.y, projected.x);
        axisEls[index].el.style.width = (26 * Math.hypot(projected.x, projected.y)) + 'px';
        axisEls[index].el.style.transform = 'rotate(' + angle + 'rad)';
        axisEls[index].caption.style.transform = 'translateY(-50%) rotate(' + -angle + 'rad)';
        axisEls[index].el.style.opacity = String(0.55 + 0.45 * (projected.z + 1) / 2);
      });
      renderer.render(scene, camera);
    }

    resize();
    setLayout('separated');
    animate();
    return {
      setSelection(value) { selection = value || null; repaintSelection(); },
      setLayout,
      setColors,
      setConnectors(value) { connectorsVisible = Boolean(value); transport.visible = connectorsVisible; },
      resize,
      projectNode,
      projectConnector,
      inspect() {
        return { layout, nodeCounts: trees.map(tree => tree.nodes.length), edgeCounts: trees.map(tree => tree.edges.length), connectorCount: coupling.length, mismatchConnectorCount:coupling.filter(c=>c.correct===false).length, connectorsVisible, selection, canvasWidth: width, canvasHeight: height, nativeToSceneScale: scale, cameraPosition: camera.position.toArray() };
      },
      destroy() {
        disposed = true;
        cancelAnimationFrame(animationFrame);
        resizeObserver.disconnect();
        controls.dispose();
        window.removeEventListener('pointerup', onPointerUp);
        canvas.removeEventListener('pointerdown', onPointerDown);
        canvas.removeEventListener('pointermove', onPointerMove);
        canvas.removeEventListener('pointerleave', onPointerLeave);
        canvas.removeEventListener('pointercancel', onPointerCancel);
        canvas.removeEventListener('keydown', onKeyDown);
        resources.forEach(resource => resource.dispose());
        renderer.dispose();
        renderer.forceContextLoss();
        canvas.remove();
        labels.forEach(label => label.remove());
        triad.remove();
      },
    };
  };
})();
