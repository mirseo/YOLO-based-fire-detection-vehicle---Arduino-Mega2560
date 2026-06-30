pub fn rgba_to_nv12(rgba: &[u8], src_stride: usize, width: usize, height: usize, nv12: &mut [u8]) {
    let y_plane_len = width * height;
    let (y_plane, uv_plane) = nv12.split_at_mut(y_plane_len);

    for row in 0..height {
        let src_row = &rgba[row * src_stride..row * src_stride + width * 4];
        let y_row = &mut y_plane[row * width..(row + 1) * width];
        for col in 0..width {
            let r = i32::from(src_row[col * 4]);
            let g = i32::from(src_row[col * 4 + 1]);
            let b = i32::from(src_row[col * 4 + 2]);
            let y = ((66 * r + 129 * g + 25 * b + 128) >> 8) + 16;
            y_row[col] = y.clamp(0, 255) as u8;
        }
    }

    let chroma_rows = height / 2;
    let chroma_cols = width / 2;
    for crow in 0..chroma_rows {
        let src_row0 = &rgba[crow * 2 * src_stride..crow * 2 * src_stride + width * 4];
        let src_row1 = &rgba[(crow * 2 + 1) * src_stride..(crow * 2 + 1) * src_stride + width * 4];
        let uv_row = &mut uv_plane[crow * width..(crow + 1) * width];
        for ccol in 0..chroma_cols {
            let i0 = ccol * 8;
            let i1 = ccol * 8 + 4;
            let r = i32::from(src_row0[i0])
                + i32::from(src_row0[i1])
                + i32::from(src_row1[i0])
                + i32::from(src_row1[i1]);
            let g = i32::from(src_row0[i0 + 1])
                + i32::from(src_row0[i1 + 1])
                + i32::from(src_row1[i0 + 1])
                + i32::from(src_row1[i1 + 1]);
            let b = i32::from(src_row0[i0 + 2])
                + i32::from(src_row0[i1 + 2])
                + i32::from(src_row1[i0 + 2])
                + i32::from(src_row1[i1 + 2]);
            let u = ((-38 * r - 74 * g + 112 * b + 512) >> 10) + 128;
            let v = ((112 * r - 94 * g - 18 * b + 512) >> 10) + 128;
            uv_row[ccol * 2] = u.clamp(0, 255) as u8;
            uv_row[ccol * 2 + 1] = v.clamp(0, 255) as u8;
        }
    }
}

pub fn even_dim(value: usize) -> usize {
    if value.is_multiple_of(2) {
        value
    } else {
        value.saturating_sub(1)
    }
}
