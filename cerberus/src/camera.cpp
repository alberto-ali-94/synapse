#include "camera.h"

#include <libcamera/camera.h>
#include <libcamera/camera_manager.h>
#include <libcamera/framebuffer.h>
#include <libcamera/framebuffer_allocator.h>
#include <libcamera/pixel_format.h>
#include <libcamera/request.h>

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>

#include <sys/mman.h>
#include <unistd.h>
#ifdef __linux__
#include <linux/dma-buf.h>
#include <sys/ioctl.h>
#endif

namespace cerberus_camera_internal {

inline int rgb_size(unsigned int width, unsigned int height, std::size_t *size)
{
    if (!size || !width || !height)
        return -EINVAL;
    const auto limit = std::numeric_limits<std::size_t>::max();
    if (static_cast<std::size_t>(width) > limit / height)
        return -EOVERFLOW;
    const auto count = static_cast<std::size_t>(width) * height;
    if (count > limit / 3)
        return -EOVERFLOW;
    *size = count * 3;
    return 0;
}

/* libcamera XRGB8888 follows DRM's little-endian packed definition:
 * memory bytes are B,G,R,X. The unused X byte is discarded. */
inline int xrgb_to_rgb(const std::uint8_t *source, std::size_t source_size,
                       std::size_t stride, unsigned int width,
                       unsigned int height, std::uint8_t *dest,
                       std::size_t capacity)
{
    std::size_t required;
    const int rc = rgb_size(width, height, &required);
    if (rc)
        return rc;
    if (!source || !dest || capacity < required)
        return -EINVAL;
    const auto limit = std::numeric_limits<std::size_t>::max();
    if (static_cast<std::size_t>(width) > limit / 4)
        return -EOVERFLOW;
    const auto row_bytes = static_cast<std::size_t>(width) * 4;
    if (stride < row_bytes)
        return -EINVAL;
    const auto rows_before_last = static_cast<std::size_t>(height - 1);
    if (rows_before_last && stride > (limit - row_bytes) / rows_before_last)
        return -EOVERFLOW;
    if (source_size < rows_before_last * stride + row_bytes)
        return -EINVAL;
    for (unsigned int y = 0; y < height; ++y) {
        const auto *row = source + static_cast<std::size_t>(y) * stride;
        auto *out = dest + static_cast<std::size_t>(y) * width * 3;
        for (unsigned int x = 0; x < width; ++x) {
            const auto input = static_cast<std::size_t>(x) * 4;
            const auto output = static_cast<std::size_t>(x) * 3;
            out[output] = row[input + 2];
            out[output + 1] = row[input + 1];
            out[output + 2] = row[input];
        }
    }
    return 0;
}

} // namespace cerberus_camera_internal

namespace {
std::mutex api_mutex;

struct CameraError : std::runtime_error {
    int code;
    CameraError(int value, const std::string &message)
        : std::runtime_error(message), code(value < 0 ? value : -EIO) {}
};

void check(int rc, const char *stage)
{
    if (rc < 0)
        throw CameraError(rc, std::string(stage) + ": " + std::to_string(rc));
}

void message(char *out, std::size_t size, const char *text) noexcept
{
    if (out && size)
        std::snprintf(out, size, "%s", text);
}

/* A frame plane's offset need not be page aligned. Map the aligned region and
 * expose only the plane itself. Every successful DMA sync START is paired with
 * END, including exception paths. */
class MappedPlane {
public:
    explicit MappedPlane(const libcamera::FrameBuffer::Plane &plane)
    {
        if (!plane.fd.isValid() || !plane.length ||
            plane.offset == libcamera::FrameBuffer::Plane::kInvalidOffset)
            throw CameraError(-EINVAL, "Invalid frame plane");
        fd_ = plane.fd.get();
        const long page = sysconf(_SC_PAGESIZE);
        if (page <= 0)
            throw CameraError(-EIO, "Cannot determine memory page size");
        const auto page_size = static_cast<std::size_t>(page);
        const auto offset = static_cast<std::size_t>(plane.offset);
        const auto aligned = offset / page_size * page_size;
        delta_ = offset - aligned;
        if (plane.length > std::numeric_limits<std::size_t>::max() - delta_ ||
            aligned > static_cast<std::uintmax_t>(std::numeric_limits<off_t>::max()))
            throw CameraError(-EOVERFLOW, "Frame mapping is too large");
        length_ = delta_ + plane.length;
        address_ = mmap(nullptr, length_, PROT_READ, MAP_SHARED, fd_,
                        static_cast<off_t>(aligned));
        if (address_ == MAP_FAILED)
            throw CameraError(-errno, "Cannot map frame memory");
        const int rc = sync(true);
        if (rc < 0) {
            munmap(address_, length_);
            address_ = MAP_FAILED;
            throw CameraError(rc, "Cannot start CPU access to frame memory");
        }
        syncing_ = true;
    }

    ~MappedPlane()
    {
        if (syncing_)
            (void)sync(false);
        if (address_ != MAP_FAILED)
            munmap(address_, length_);
    }

    const std::uint8_t *data() const
    {
        return static_cast<const std::uint8_t *>(address_) + delta_;
    }

    void end_access()
    {
        const int rc = sync(false);
        if (rc >= 0)
            syncing_ = false;
        check(rc, "Cannot finish CPU access to frame memory");
    }

    MappedPlane(const MappedPlane &) = delete;
    MappedPlane &operator=(const MappedPlane &) = delete;

private:
    int sync(bool start)
    {
#ifdef __linux__
        struct dma_buf_sync operation {};
        operation.flags = DMA_BUF_SYNC_READ |
                          (start ? DMA_BUF_SYNC_START : DMA_BUF_SYNC_END);
        int result;
        do {
            result = ioctl(fd_, DMA_BUF_IOCTL_SYNC, &operation);
        } while (result < 0 && errno == EINTR);
        return result < 0 ? -errno : 0;
#else
        (void)start;
        return -ENOSYS;
#endif
    }

    int fd_ = -1;
    void *address_ = MAP_FAILED;
    std::size_t length_ = 0;
    std::size_t delta_ = 0;
    bool syncing_ = false;
};

class Capture {
public:
    ~Capture() { (void)finish(); }

    std::vector<std::uint8_t> run(unsigned int width, unsigned int height,
                                   unsigned int timeout_ms, std::size_t bytes)
    {
        check(manager_.start(), "Starting camera manager");
        manager_started_ = true;
        {
            const auto cameras = manager_.cameras();
            if (cameras.empty())
                throw CameraError(-ENODEV, "No camera is available");
            camera_ = cameras.front();
        }
        check(camera_->acquire(), "Acquiring camera");
        acquired_ = true;
        config_ = camera_->generateConfiguration({libcamera::StreamRole::Viewfinder});
        if (!config_ || config_->empty())
            throw CameraError(-ENOTSUP, "Cannot generate a camera configuration");
        auto &cfg = config_->at(0);
        const auto format = libcamera::PixelFormat::fromString("XRGB8888");
        if (!format.isValid())
            throw CameraError(-ENOTSUP, "XRGB8888 is unavailable in this libcamera build");
        cfg.size.width = width;
        cfg.size.height = height;
        cfg.pixelFormat = format;
        if (config_->validate() == libcamera::CameraConfiguration::Invalid ||
            cfg.size.width != width || cfg.size.height != height ||
            cfg.pixelFormat != format)
            throw CameraError(-ENOTSUP, "Camera cannot provide the requested size and format");
        check(camera_->configure(config_.get()), "Applying camera configuration");
        auto *stream = cfg.stream();
        if (!stream)
            throw CameraError(-EIO, "Configuration did not provide a stream");

        allocator_ = std::make_unique<libcamera::FrameBufferAllocator>(camera_);
        const int count = allocator_->allocate(stream);
        check(count, "Allocating frame buffers");
        const auto &buffers = allocator_->buffers(stream);
        if (count == 0 || buffers.empty())
            throw CameraError(-ENOMEM, "No frame buffers were allocated");
        completed_queue_.resize(buffers.size(), nullptr);
        requests_.reserve(buffers.size());
        for (std::size_t i = 0; i < buffers.size(); ++i) {
            auto request = camera_->createRequest(static_cast<std::uint64_t>(i));
            if (!request)
                throw CameraError(-ENOMEM, "Cannot create a capture request");
            check(request->addBuffer(stream, buffers[i].get()), "Attaching frame buffer");
            requests_.push_back(std::move(request));
        }
        camera_->requestCompleted.connect(this, &Capture::completed);
        connected_ = true;
        check(camera_->start(), "Starting capture");
        running_ = true;
        const auto deadline = std::chrono::steady_clock::now() +
                              std::chrono::milliseconds(timeout_ms);
        for (const auto &request : requests_)
            check(camera_->queueRequest(request.get()), "Queueing capture request");

        libcamera::FrameBuffer *selected = nullptr;
        unsigned int successful_frames = 0;
        while (!selected) {
            libcamera::Request *request;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                const auto available = [this] { return completed_count_ != 0 || queue_error_; };
                if (!cv_.wait_until(lock, deadline, available))
                    throw CameraError(-ETIMEDOUT, "Timed out waiting for camera frames");
                if (std::chrono::steady_clock::now() >= deadline)
                    throw CameraError(-ETIMEDOUT, "Timed out waiting for camera frames");
                if (queue_error_)
                    throw CameraError(-EIO, "Unexpected camera completion queue overflow");
                request = completed_queue_[completed_head_];
                completed_head_ = (completed_head_ + 1) % completed_queue_.size();
                --completed_count_;
            }
            if (request->status() != libcamera::Request::RequestComplete)
                throw CameraError(-EIO, "Camera cancelled a capture request");
            auto *buffer = request->findBuffer(stream);
            if (!buffer)
                throw CameraError(-EIO, "Completed request has no frame buffer");
            const auto status = buffer->metadata().status;
            if (status == libcamera::FrameMetadata::FrameError ||
                status == libcamera::FrameMetadata::FrameCancelled)
                throw CameraError(-EIO, "Camera reported an invalid frame");
            if (status == libcamera::FrameMetadata::FrameSuccess &&
                ++successful_frames > 8) {
                selected = buffer;
                break;
            }
            request->reuse(libcamera::Request::ReuseBuffers);
            check(camera_->queueRequest(request), "Requeueing capture request");
        }

        check(camera_->stop(), "Stopping capture");
        running_ = false;
        const auto planes = selected->planes();
        const auto metadata = selected->metadata().planes();
        if (planes.size() != 1 || metadata.size() != 1 ||
            metadata[0].bytesused > planes[0].length)
            throw CameraError(-ENOTSUP, "Unexpected frame memory layout");
        std::vector<std::uint8_t> rgb(bytes);
        {
            MappedPlane mapping(planes[0]);
            check(cerberus_camera_internal::xrgb_to_rgb(
                      mapping.data(), metadata[0].bytesused, cfg.stride,
                      width, height, rgb.data(), rgb.size()),
                  "Converting camera frame to packed RGB");
            mapping.end_access();
        }
        check(finish(), "Releasing camera resources");
        return rgb;
    }

private:
    void completed(libcamera::Request *request)
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (completed_count_ == completed_queue_.size()) {
                queue_error_ = true;
            } else {
                const auto tail = (completed_head_ + completed_count_) % completed_queue_.size();
                completed_queue_[tail] = request;
                ++completed_count_;
            }
        }
        cv_.notify_one();
    }

    int finish() noexcept
    {
        int result = 0;
        if (running_) {
            result = camera_->stop();
            running_ = false;
        }
        if (connected_) {
            camera_->requestCompleted.disconnect(this);
            connected_ = false;
        }
        requests_.clear();
        allocator_.reset();
        config_.reset();
        if (acquired_) {
            const int rc = camera_->release();
            if (result == 0)
                result = rc;
            acquired_ = false;
        }
        camera_.reset();
        if (manager_started_) {
            manager_.stop();
            manager_started_ = false;
        }
        return result;
    }

    libcamera::CameraManager manager_;
    std::shared_ptr<libcamera::Camera> camera_;
    std::unique_ptr<libcamera::CameraConfiguration> config_;
    std::unique_ptr<libcamera::FrameBufferAllocator> allocator_;
    std::vector<std::unique_ptr<libcamera::Request>> requests_;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::vector<libcamera::Request *> completed_queue_;
    std::size_t completed_head_ = 0;
    std::size_t completed_count_ = 0;
    bool queue_error_ = false;
    bool manager_started_ = false;
    bool acquired_ = false;
    bool connected_ = false;
    bool running_ = false;
};
} // namespace

extern "C" int cerberus_camera_rgb_size(unsigned int width, unsigned int height,
                                         std::size_t *size)
{
    return cerberus_camera_internal::rgb_size(width, height, size);
}

extern "C" int cerberus_camera_capture_rgb(unsigned int width, unsigned int height,
                                            std::uint8_t *pixels, std::size_t capacity,
                                            unsigned int timeout_ms,
                                            char *error, std::size_t error_size)
{
    if (error_size && !error)
        return -EINVAL;
    message(error, error_size, "");
    std::size_t bytes;
    const int rc = cerberus_camera_rgb_size(width, height, &bytes);
    if (rc != 0 || !pixels || (rc == 0 && capacity < bytes) ||
        timeout_ms == 0 || timeout_ms > 60000) {
        message(error, error_size, "Invalid dimensions, capacity, pointer or timeout");
        return rc != 0 ? rc : -EINVAL;
    }
    try {
        std::lock_guard<std::mutex> lock(api_mutex);
        Capture capture;
        const auto rgb = capture.run(width, height, timeout_ms, bytes);
        std::memcpy(pixels, rgb.data(), bytes);
        return 0;
    } catch (const CameraError &exception) {
        message(error, error_size, exception.what());
        return exception.code;
    } catch (const std::bad_alloc &) {
        message(error, error_size, "Not enough memory to acquire an image");
        return -ENOMEM;
    } catch (const std::exception &exception) {
        message(error, error_size, exception.what());
        return -EIO;
    } catch (...) {
        message(error, error_size, "Unexpected camera error");
        return -EIO;
    }
}
