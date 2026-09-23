/*
 * 纯 JS 手写数字 CNN 前向 + MNIST 风格预处理
 * 与 PyTorch 训练的小 CNN 结构一一对应：
 *   conv1(1->16,3x3,pad1)+ReLU+maxpool2 -> conv2(16->32,3x3,pad1)+ReLU+maxpool2
 *   -> flatten(1568) -> fc1(1568->128)+ReLU -> fc2(128->10)
 * 权重来自 mnist_weights.json（PyTorch 导出）。推理时 Dropout 跳过。
 */
function _conv2d(x, w, b, inC, outC, k, pad) {
  const H = x[0].length, W = x[0][0].length;
  const OH = H + 2 * pad - k + 1, OW = W + 2 * pad - k + 1;
  const out = [];
  for (let oc = 0; oc < outC; oc++) {
    const plane = [];
    for (let oy = 0; oy < OH; oy++) {
      const row = new Array(OW);
      for (let ox = 0; ox < OW; ox++) {
        let s = b[oc];
        for (let ic = 0; ic < inC; ic++) {
          const wp = w[oc][ic];
          for (let ky = 0; ky < k; ky++) {
            const yy = oy + ky - pad;
            if (yy < 0 || yy >= H) continue;
            const xrow = x[ic][yy];
            for (let kx = 0; kx < k; kx++) {
              const xx = ox + kx - pad;
              if (xx < 0 || xx >= W) continue;
              s += wp[ky][kx] * xrow[xx];
            }
          }
        }
        row[ox] = s;
      }
      plane.push(row);
    }
    out.push(plane);
  }
  return out;
}
function _relu3(t) { for (const p of t) for (const r of p) for (let i = 0; i < r.length; i++) if (r[i] < 0) r[i] = 0; return t; }
function _maxpool2(t) {
  const C = t.length, H = t[0].length, W = t[0][0].length, out = [];
  for (let c = 0; c < C; c++) {
    const p = [];
    for (let y = 0; y < H; y += 2) {
      const row = [];
      for (let x = 0; x < W; x += 2)
        row.push(Math.max(t[c][y][x], t[c][y + 1][x], t[c][y][x + 1], t[c][y + 1][x + 1]));
      p.push(row);
    }
    out.push(p);
  }
  return out;
}
function _linear(vec, w, b) {
  const out = new Array(w.length);
  for (let o = 0; o < w.length; o++) {
    let s = b[o]; const wo = w[o];
    for (let i = 0; i < vec.length; i++) s += wo[i] * vec[i];
    out[o] = s;
  }
  return out;
}
function mnistForward(W, img) {
  let x = [img];                                   // [1][28][28]
  x = _relu3(_conv2d(x, W.conv1.w, W.conv1.b, 1, 16, 3, 1)); x = _maxpool2(x);   // 16x14x14
  x = _relu3(_conv2d(x, W.conv2.w, W.conv2.b, 16, 32, 3, 1)); x = _maxpool2(x);  // 32x7x7
  const flat = []; for (const p of x) for (const r of p) for (const v of r) flat.push(v);
  const h = _linear(flat, W.fc1.w, W.fc1.b).map(v => v > 0 ? v : 0);
  return _linear(h, W.fc2.w, W.fc2.b);             // 10 logits
}
function mnistSoftmax(a) {
  const m = Math.max.apply(null, a);
  const e = a.map(v => Math.exp(v - m));
  const s = e.reduce((x, y) => x + y, 0);
  return e.map(v => v / s);
}

/* 把画布上的手绘数字转成 MNIST 风格 28x28：找外接框→等比缩到~20px→居中→白字黑底 */
function preprocessCanvas(canvas) {
  const ctx = canvas.getContext('2d');
  const { width: cw, height: ch } = canvas;
  const data = ctx.getImageData(0, 0, cw, ch).data;
  const ink = new Float32Array(cw * ch);
  let minX = cw, minY = ch, maxX = -1, maxY = -1;
  for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) {
    const i = (y * cw + x) * 4;
    const gray = (data[i] + data[i + 1] + data[i + 2]) / 3;   // 白底黑字
    const v = (255 - gray) / 255;                              // 笔画→高
    ink[y * cw + x] = v;
    if (v > 0.15) { if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; }
  }
  const out = Array.from({ length: 28 }, () => new Array(28).fill(0));
  if (maxX < 0) return out;                                     // 没画东西
  const bw = maxX - minX + 1, bh = maxY - minY + 1;
  const scale = 20 / Math.max(bw, bh);                          // 长边缩到 20
  const sw = Math.max(1, Math.round(bw * scale)), sh = Math.max(1, Math.round(bh * scale));
  const offX = Math.round((28 - sw) / 2), offY = Math.round((28 - sh) / 2);
  for (let y = 0; y < sh; y++) for (let x = 0; x < sw; x++) {
    const sx = minX + Math.floor(x / scale), sy = minY + Math.floor(y / scale);
    const gx = offX + x, gy = offY + y;
    if (gx >= 0 && gx < 28 && gy >= 0 && gy < 28) out[gy][gx] = ink[sy * cw + sx];
  }
  return out;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { mnistForward, mnistSoftmax, preprocessCanvas };
}
