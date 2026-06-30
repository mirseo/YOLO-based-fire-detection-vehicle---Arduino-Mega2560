use std::mem::ManuallyDrop;
use std::ptr;
use std::sync::OnceLock;

use anyhow::{Result, anyhow};
use windows::Win32::Foundation::VARIANT_BOOL;
use windows::Win32::Media::MediaFoundation::{
    CODECAPI_AVEncCommonMeanBitRate, CODECAPI_AVEncCommonRateControlMode, CODECAPI_AVEncMPVGOPSize,
    CODECAPI_AVLowLatencyMode, ICodecAPI, IMFMediaEvent, IMFMediaEventGenerator, IMFMediaType,
    IMFSample, IMFTransform, MEDIA_EVENT_GENERATOR_GET_EVENT_FLAGS, METransformDrainComplete,
    METransformHaveOutput, METransformNeedInput, MF_API_VERSION, MF_E_NO_EVENTS_AVAILABLE,
    MF_E_TRANSFORM_NEED_MORE_INPUT, MF_E_TRANSFORM_STREAM_CHANGE, MF_EVENT_FLAG_NO_WAIT,
    MF_MT_AVG_BITRATE, MF_MT_FRAME_RATE, MF_MT_FRAME_SIZE, MF_MT_INTERLACE_MODE, MF_MT_MAJOR_TYPE,
    MF_MT_MPEG2_PROFILE, MF_MT_PIXEL_ASPECT_RATIO, MF_MT_SUBTYPE, MF_SDK_VERSION,
    MF_TRANSFORM_ASYNC, MF_TRANSFORM_ASYNC_UNLOCK, MFCreateMediaType, MFCreateMemoryBuffer,
    MFCreateSample, MFMediaType_Video, MFSTARTUP_LITE, MFStartup, MFT_CATEGORY_VIDEO_ENCODER,
    MFT_ENUM_FLAG_ASYNCMFT, MFT_ENUM_FLAG_HARDWARE, MFT_ENUM_FLAG_SORTANDFILTER,
    MFT_ENUM_FLAG_SYNCMFT, MFT_MESSAGE_COMMAND_FLUSH, MFT_MESSAGE_NOTIFY_BEGIN_STREAMING,
    MFT_MESSAGE_NOTIFY_END_OF_STREAM, MFT_MESSAGE_NOTIFY_END_STREAMING,
    MFT_MESSAGE_NOTIFY_START_OF_STREAM, MFT_OUTPUT_DATA_BUFFER,
    MFT_OUTPUT_DATA_BUFFER_FORMAT_CHANGE, MFT_OUTPUT_STREAM_PROVIDES_SAMPLES,
    MFT_REGISTER_TYPE_INFO, MFTEnumEx, MFVideoFormat_H264, MFVideoFormat_NV12,
    MFVideoInterlace_Progressive, eAVEncCommonRateControlMode_CBR, eAVEncH264VProfile_Base,
};
use windows::Win32::System::Com::{COINIT_MULTITHREADED, CoInitializeEx, CoTaskMemFree};
use windows::Win32::System::Variant::{
    VARIANT, VARIANT_0, VARIANT_0_0, VARIANT_0_0_0, VT_BOOL, VT_UI4,
};
use windows::core::Interface;

use crate::modules::config::TARGET_BITRATE_BPS;
use crate::modules::pixel::rgba_to_nv12;

static MF_INITIALIZED: OnceLock<()> = OnceLock::new();

fn ensure_mf_initialized() -> Result<()> {
    if MF_INITIALIZED.get().is_some() {
        return Ok(());
    }
    unsafe {
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        MFStartup((MF_SDK_VERSION << 16) | MF_API_VERSION, MFSTARTUP_LITE)
            .map_err(|e| anyhow!("MFStartup failed: {e}"))?;
    }
    let _ = MF_INITIALIZED.set(());
    Ok(())
}

fn variant_u32(value: u32) -> VARIANT {
    VARIANT {
        Anonymous: VARIANT_0 {
            Anonymous: ManuallyDrop::new(VARIANT_0_0 {
                vt: VT_UI4,
                wReserved1: 0,
                wReserved2: 0,
                wReserved3: 0,
                Anonymous: VARIANT_0_0_0 { ulVal: value },
            }),
        },
    }
}

fn variant_bool(value: bool) -> VARIANT {
    VARIANT {
        Anonymous: VARIANT_0 {
            Anonymous: ManuallyDrop::new(VARIANT_0_0 {
                vt: VT_BOOL,
                wReserved1: 0,
                wReserved2: 0,
                wReserved3: 0,
                Anonymous: VARIANT_0_0_0 {
                    boolVal: VARIANT_BOOL(if value { -1 } else { 0 }),
                },
            }),
        },
    }
}

fn pack_hi_lo(hi: u32, lo: u32) -> u64 {
    (u64::from(hi) << 32) | u64::from(lo)
}

pub struct MfH264Encoder {
    transform: IMFTransform,
    event_gen: Option<IMFMediaEventGenerator>,
    input_stream_id: u32,
    output_stream_id: u32,
    width: u32,
    height: u32,
    fps: u32,
    nv12: Vec<u8>,
    frame_index: u64,
    annexb: Vec<u8>,
    need_input_pending: u32,
}

unsafe impl Send for MfH264Encoder {}

enum EventPumpError {
    NoEvents,
    Other(anyhow::Error),
}

impl MfH264Encoder {
    pub fn new(width: u32, height: u32, fps: u32) -> Result<Self> {
        ensure_mf_initialized()?;
        let (transform, is_async) = unsafe { create_h264_encoder() }?;

        if is_async {
            unsafe { unlock_async(&transform) }?;
        }

        unsafe {
            configure_codec_api(&transform, fps)?;
            configure_output_type(&transform, width, height, fps)?;
            configure_input_type(&transform, width, height, fps)?;
        }

        let (input_stream_id, output_stream_id) = unsafe { resolve_stream_ids(&transform) };

        let event_gen = if is_async {
            Some(transform.cast::<IMFMediaEventGenerator>()?)
        } else {
            None
        };

        unsafe {
            transform.ProcessMessage(MFT_MESSAGE_COMMAND_FLUSH, 0)?;
            transform.ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0)?;
            transform.ProcessMessage(MFT_MESSAGE_NOTIFY_START_OF_STREAM, 0)?;
        }

        let nv12_len = (width as usize) * (height as usize) * 3 / 2;
        Ok(Self {
            transform,
            event_gen,
            input_stream_id,
            output_stream_id,
            width,
            height,
            fps,
            nv12: vec![0u8; nv12_len],
            frame_index: 0,
            annexb: Vec::with_capacity(256 * 1024),
            need_input_pending: 0,
        })
    }

    pub fn encode_rgba(&mut self, rgba: &[u8], src_stride: usize) -> Result<Vec<u8>> {
        rgba_to_nv12(
            rgba,
            src_stride,
            self.width as usize,
            self.height as usize,
            &mut self.nv12,
        );
        let sample = unsafe { build_input_sample(&self.nv12, self.frame_index, self.fps) }?;
        self.frame_index += 1;

        self.annexb.clear();

        if self.event_gen.is_some() {
            self.encode_async(&sample)?;
        } else {
            unsafe {
                self.transform
                    .ProcessInput(self.input_stream_id, &sample, 0)?;
            }
            unsafe {
                drain_output(
                    &self.transform,
                    self.output_stream_id,
                    &mut self.annexb,
                    false,
                )
            }?;
        }
        Ok(std::mem::take(&mut self.annexb))
    }

    fn encode_async(&mut self, sample: &IMFSample) -> Result<()> {
        while self.need_input_pending == 0 {
            match self.pump_one_event(MEDIA_EVENT_GENERATOR_GET_EVENT_FLAGS(0)) {
                Ok(()) => {}
                Err(EventPumpError::NoEvents) => {}
                Err(EventPumpError::Other(e)) => return Err(e),
            }
        }
        self.need_input_pending -= 1;
        unsafe {
            self.transform
                .ProcessInput(self.input_stream_id, sample, 0)?;
        }
        loop {
            match self.pump_one_event(MF_EVENT_FLAG_NO_WAIT) {
                Ok(()) => continue,
                Err(EventPumpError::NoEvents) => break,
                Err(EventPumpError::Other(e)) => return Err(e),
            }
        }
        Ok(())
    }

    fn pump_one_event(
        &mut self,
        flags: MEDIA_EVENT_GENERATOR_GET_EVENT_FLAGS,
    ) -> std::result::Result<(), EventPumpError> {
        let event_gen = self
            .event_gen
            .as_ref()
            .ok_or_else(|| EventPumpError::Other(anyhow!("event generator missing")))?;
        let event: IMFMediaEvent = match unsafe { event_gen.GetEvent(flags) } {
            Ok(ev) => ev,
            Err(err) => {
                if err.code() == MF_E_NO_EVENTS_AVAILABLE {
                    return Err(EventPumpError::NoEvents);
                }
                return Err(EventPumpError::Other(anyhow!("GetEvent failed: {err}")));
            }
        };
        let event_type = unsafe { event.GetType() }
            .map_err(|e| EventPumpError::Other(anyhow!("GetType failed: {e}")))?;
        if event_type == METransformNeedInput.0 as u32 {
            self.need_input_pending = self.need_input_pending.saturating_add(1);
        } else if event_type == METransformHaveOutput.0 as u32 {
            unsafe {
                drain_output(
                    &self.transform,
                    self.output_stream_id,
                    &mut self.annexb,
                    true,
                )
                .map_err(EventPumpError::Other)?;
            }
        } else if event_type == METransformDrainComplete.0 as u32 {
        }
        Ok(())
    }
}

impl Drop for MfH264Encoder {
    fn drop(&mut self) {
        unsafe {
            let _ = self
                .transform
                .ProcessMessage(MFT_MESSAGE_NOTIFY_END_OF_STREAM, 0);
            let _ = self
                .transform
                .ProcessMessage(MFT_MESSAGE_NOTIFY_END_STREAMING, 0);
        }
    }
}

unsafe fn create_h264_encoder() -> Result<(IMFTransform, bool)> {
    let input_info = MFT_REGISTER_TYPE_INFO {
        guidMajorType: MFMediaType_Video,
        guidSubtype: MFVideoFormat_NV12,
    };
    let output_info = MFT_REGISTER_TYPE_INFO {
        guidMajorType: MFMediaType_Video,
        guidSubtype: MFVideoFormat_H264,
    };

    let attempts = [
        (
            MFT_ENUM_FLAG_HARDWARE | MFT_ENUM_FLAG_ASYNCMFT | MFT_ENUM_FLAG_SORTANDFILTER,
            true,
        ),
        (
            MFT_ENUM_FLAG_HARDWARE | MFT_ENUM_FLAG_SYNCMFT | MFT_ENUM_FLAG_SORTANDFILTER,
            false,
        ),
        (MFT_ENUM_FLAG_SYNCMFT | MFT_ENUM_FLAG_SORTANDFILTER, false),
    ];

    for (flags, is_async) in attempts {
        let mut activates_ptr = ptr::null_mut();
        let mut count: u32 = 0;
        let enum_result = unsafe {
            MFTEnumEx(
                MFT_CATEGORY_VIDEO_ENCODER,
                flags,
                Some(&input_info),
                Some(&output_info),
                &mut activates_ptr,
                &mut count,
            )
        };
        if enum_result.is_err() || count == 0 || activates_ptr.is_null() {
            if !activates_ptr.is_null() {
                unsafe { CoTaskMemFree(Some(activates_ptr as *const _)) };
            }
            continue;
        }
        let slot = unsafe { &*activates_ptr };
        let activate = slot.clone();
        for i in 0..count as isize {
            let entry = unsafe { activates_ptr.offset(i) };
            unsafe { ptr::drop_in_place(entry) };
        }
        unsafe { CoTaskMemFree(Some(activates_ptr as *const _)) };
        let Some(activate) = activate else { continue };
        let transform: IMFTransform = unsafe { activate.ActivateObject() }?;
        return Ok((transform, is_async));
    }
    Err(anyhow!("no H.264 encoder MFT found"))
}

unsafe fn unlock_async(transform: &IMFTransform) -> Result<()> {
    let attrs = unsafe { transform.GetAttributes() }?;
    let is_async = unsafe { attrs.GetUINT32(&MF_TRANSFORM_ASYNC) }.unwrap_or(0);
    if is_async == 1 {
        unsafe { attrs.SetUINT32(&MF_TRANSFORM_ASYNC_UNLOCK, 1) }?;
    }
    Ok(())
}

unsafe fn configure_codec_api(transform: &IMFTransform, fps: u32) -> Result<()> {
    let Ok(codec_api) = transform.cast::<ICodecAPI>() else {
        return Ok(());
    };
    let low_latency = variant_bool(true);
    let _ = unsafe { codec_api.SetValue(&CODECAPI_AVLowLatencyMode, &low_latency) };
    let rc = variant_u32(eAVEncCommonRateControlMode_CBR.0 as u32);
    let _ = unsafe { codec_api.SetValue(&CODECAPI_AVEncCommonRateControlMode, &rc) };
    let bitrate = variant_u32(TARGET_BITRATE_BPS);
    let _ = unsafe { codec_api.SetValue(&CODECAPI_AVEncCommonMeanBitRate, &bitrate) };
    let gop = variant_u32(fps.saturating_mul(2).max(1));
    let _ = unsafe { codec_api.SetValue(&CODECAPI_AVEncMPVGOPSize, &gop) };
    Ok(())
}

unsafe fn configure_output_type(
    transform: &IMFTransform,
    width: u32,
    height: u32,
    fps: u32,
) -> Result<()> {
    let media: IMFMediaType = unsafe { MFCreateMediaType() }?;
    unsafe {
        media.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Video)?;
        media.SetGUID(&MF_MT_SUBTYPE, &MFVideoFormat_H264)?;
        media.SetUINT32(&MF_MT_AVG_BITRATE, TARGET_BITRATE_BPS)?;
        media.SetUINT64(&MF_MT_FRAME_SIZE, pack_hi_lo(width, height))?;
        media.SetUINT64(&MF_MT_FRAME_RATE, pack_hi_lo(fps, 1))?;
        media.SetUINT64(&MF_MT_PIXEL_ASPECT_RATIO, pack_hi_lo(1, 1))?;
        media.SetUINT32(&MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive.0 as u32)?;
        media.SetUINT32(&MF_MT_MPEG2_PROFILE, eAVEncH264VProfile_Base.0 as u32)?;
        transform.SetOutputType(0, &media, 0)?;
    }
    Ok(())
}

unsafe fn configure_input_type(
    transform: &IMFTransform,
    width: u32,
    height: u32,
    fps: u32,
) -> Result<()> {
    let media: IMFMediaType = unsafe { MFCreateMediaType() }?;
    unsafe {
        media.SetGUID(&MF_MT_MAJOR_TYPE, &MFMediaType_Video)?;
        media.SetGUID(&MF_MT_SUBTYPE, &MFVideoFormat_NV12)?;
        media.SetUINT64(&MF_MT_FRAME_SIZE, pack_hi_lo(width, height))?;
        media.SetUINT64(&MF_MT_FRAME_RATE, pack_hi_lo(fps, 1))?;
        media.SetUINT64(&MF_MT_PIXEL_ASPECT_RATIO, pack_hi_lo(1, 1))?;
        media.SetUINT32(&MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive.0 as u32)?;
        transform.SetInputType(0, &media, 0)?;
    }
    Ok(())
}

unsafe fn resolve_stream_ids(transform: &IMFTransform) -> (u32, u32) {
    let mut input_ids = [0u32; 1];
    let mut output_ids = [0u32; 1];
    let _ = unsafe { transform.GetStreamIDs(&mut input_ids, &mut output_ids) };
    (input_ids[0], output_ids[0])
}

unsafe fn build_input_sample(nv12: &[u8], frame_index: u64, fps: u32) -> Result<IMFSample> {
    let buffer = unsafe { MFCreateMemoryBuffer(nv12.len() as u32) }?;
    let mut buf_ptr: *mut u8 = ptr::null_mut();
    let mut max_len: u32 = 0;
    let mut cur_len: u32 = 0;
    unsafe {
        buffer.Lock(&mut buf_ptr, Some(&mut max_len), Some(&mut cur_len))?;
        ptr::copy_nonoverlapping(nv12.as_ptr(), buf_ptr, nv12.len());
        buffer.Unlock()?;
        buffer.SetCurrentLength(nv12.len() as u32)?;
    }

    let sample = unsafe { MFCreateSample() }?;
    unsafe {
        sample.AddBuffer(&buffer)?;
        let duration_100ns = 10_000_000_i64 / i64::from(fps.max(1));
        let timestamp_100ns = (frame_index as i64).saturating_mul(duration_100ns);
        sample.SetSampleTime(timestamp_100ns)?;
        sample.SetSampleDuration(duration_100ns)?;
    }
    Ok(sample)
}

unsafe fn drain_output(
    transform: &IMFTransform,
    output_stream_id: u32,
    annexb: &mut Vec<u8>,
    single_pass: bool,
) -> Result<()> {
    loop {
        let info = unsafe { transform.GetOutputStreamInfo(output_stream_id) }?;
        let provides_sample = (info.dwFlags & MFT_OUTPUT_STREAM_PROVIDES_SAMPLES.0 as u32) != 0;
        let sample_slot: Option<IMFSample> = if provides_sample {
            None
        } else {
            let buffer = unsafe { MFCreateMemoryBuffer(info.cbSize.max(1)) }?;
            let s = unsafe { MFCreateSample() }?;
            unsafe { s.AddBuffer(&buffer) }?;
            Some(s)
        };

        let mut buffers = [MFT_OUTPUT_DATA_BUFFER {
            dwStreamID: output_stream_id,
            pSample: ManuallyDrop::new(sample_slot),
            dwStatus: 0,
            pEvents: ManuallyDrop::new(None),
        }];
        let mut status: u32 = 0;
        let result = unsafe { transform.ProcessOutput(0, &mut buffers, &mut status) };

        let dw_status = buffers[0].dwStatus;
        let MFT_OUTPUT_DATA_BUFFER {
            pSample, pEvents, ..
        } = unsafe { ptr::read(&buffers[0]) };
        let produced_sample = ManuallyDrop::into_inner(pSample);
        let _events = ManuallyDrop::into_inner(pEvents);

        let format_change_flag = (dw_status & MFT_OUTPUT_DATA_BUFFER_FORMAT_CHANGE.0 as u32) != 0;

        match result {
            Ok(()) => {
                if format_change_flag {
                    unsafe { renegotiate_output_type(transform, output_stream_id) }?;
                    if single_pass {
                        return Ok(());
                    }
                    continue;
                }
                if let Some(sample) = produced_sample {
                    unsafe { append_sample_bytes(&sample, annexb) }?;
                }
                if single_pass {
                    return Ok(());
                }
            }
            Err(err) if err.code() == MF_E_TRANSFORM_NEED_MORE_INPUT => break,
            Err(err) if err.code() == MF_E_TRANSFORM_STREAM_CHANGE => {
                unsafe { renegotiate_output_type(transform, output_stream_id) }?;
                if single_pass {
                    return Ok(());
                }
                continue;
            }
            Err(err) => return Err(anyhow!("ProcessOutput failed: {err}")),
        }
    }
    Ok(())
}

unsafe fn renegotiate_output_type(transform: &IMFTransform, output_stream_id: u32) -> Result<()> {
    let mut index = 0u32;
    let mut last_err: Option<windows::core::Error> = None;
    loop {
        let media_type = match unsafe { transform.GetOutputAvailableType(output_stream_id, index) }
        {
            Ok(t) => t,
            Err(err) => {
                return Err(match last_err {
                    Some(prev) => anyhow!(
                        "renegotiate output type failed: enumerated {index} types, last SetOutputType error: {prev}, GetOutputAvailableType: {err}"
                    ),
                    None => anyhow!("renegotiate output type failed: no available types ({err})"),
                });
            }
        };
        match unsafe { transform.SetOutputType(output_stream_id, &media_type, 0) } {
            Ok(()) => return Ok(()),
            Err(err) => {
                last_err = Some(err);
                index += 1;
            }
        }
    }
}

unsafe fn append_sample_bytes(sample: &IMFSample, out: &mut Vec<u8>) -> Result<()> {
    let buffer = unsafe { sample.ConvertToContiguousBuffer() }?;
    let mut buf_ptr: *mut u8 = ptr::null_mut();
    let mut max_len: u32 = 0;
    let mut cur_len: u32 = 0;
    unsafe {
        buffer.Lock(&mut buf_ptr, Some(&mut max_len), Some(&mut cur_len))?;
        let slice = std::slice::from_raw_parts(buf_ptr, cur_len as usize);
        out.extend_from_slice(slice);
        buffer.Unlock()?;
    }
    Ok(())
}
