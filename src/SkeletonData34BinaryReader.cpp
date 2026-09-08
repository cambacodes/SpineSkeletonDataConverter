#include "SkeletonData.h"
#include <stdexcept>

namespace spine34 {

void readFloatArray(DataInput* input, int n, std::vector<float>& array) {
    if (n < 0 || static_cast<size_t>(n) > (input->end - input->cursor) / sizeof(float))
        throw std::runtime_error("Invalid float array length");
    array.resize(n, 0);
    for (int i = 0; i < n; i++)
        array[i] = readFloat(input);
}

void readShortArray(DataInput* input, std::vector<unsigned short>& array) {
    int n = readVarint(input, true);
    if (n < 0 || static_cast<size_t>(n) > (input->end - input->cursor) / 2)
        throw std::runtime_error("Invalid short array length");
    array.resize(n, 0);
    for (int i = 0; i < n; i++) {
        array[i] = readByte(input) << 8;
        array[i] |= readByte(input);
    }
}

void readVertices(DataInput* input, std::vector<float>& vertices, int vertexCount) {
    if (!readBoolean(input)) {
        readFloatArray(input, vertexCount << 1, vertices);
    } else {
        for (int i = 0; i < vertexCount; i++) {
            int boneCount = readVarint(input, true);
            vertices.push_back(boneCount);
            for (int ii = 0; ii < boneCount; ii++) {
                vertices.push_back(readVarint(input, true));
                vertices.push_back(readFloat(input));
                vertices.push_back(readFloat(input));
                vertices.push_back(readFloat(input));
            }
        }
    }
}

void readCurve(DataInput* input, TimelineFrame& frame) {
    switch (readByte(input)) {
        case CURVE_STEPPED: {
            frame.curveType = CurveType::CURVE_STEPPED;
            break;
        }
        case CURVE_BEZIER: {
            frame.curveType = CurveType::CURVE_BEZIER;
            frame.curve.push_back(readFloat(input));
            frame.curve.push_back(readFloat(input));
            frame.curve.push_back(readFloat(input));
            frame.curve.push_back(readFloat(input));
            break;
        }
    }
}

Timeline readTimeline(DataInput* input, int frameCount, int valueNum) {
    Timeline timeline;
    for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
        TimelineFrame frame;
        frame.time = readFloat(input);
        frame.value1 = readFloat(input);
        if (valueNum > 1) frame.value2 = readFloat(input);
        if (frameIndex < frameCount - 1) readCurve(input, frame);
        timeline.push_back(frame);
    }
    return timeline;
}

Skin readSkin(DataInput* input, bool defaultSkin, SkeletonData* skeletonData) {
    Skin skin;
    int slotCount = 0;
    if (defaultSkin) {
        slotCount = readVarint(input, true);
        skin.name = "default";
    } else {
        skin.name = readString(input).value();
        slotCount = readVarint(input, true);
    }
    for (int i = 0; i < slotCount; i++) {
        std::string slotName = skeletonData->slots.at(readVarint(input, true)).name.value();
        for (int ii = 0, nn = readVarint(input, true); ii < nn; ii++) {
            std::string attachmentName = readString(input).value();
            Attachment attachment;
            auto name = readString(input);
            attachment.name = (name.has_value() && !name->empty()) ? name.value() : attachmentName;
            attachment.type = static_cast<AttachmentType>(readByte(input));
            switch (attachment.type) {
                case AttachmentType_Region: {
                    RegionAttachment region;
                    auto path = readString(input);
                    attachment.path = (path.has_value() && !path->empty()) ? path.value() : attachment.name;
                    region.rotation = readFloat(input);
                    region.x = readFloat(input);
                    region.y = readFloat(input);
                    region.scaleX = readFloat(input);
                    region.scaleY = readFloat(input);
                    region.width = readFloat(input);
                    region.height = readFloat(input);
                    Color color = readColor(input);
                    if (color != Color{0xff, 0xff, 0xff, 0xff}) region.color = color;
                    attachment.data = region;
                    break;
                }
                case AttachmentType_Boundingbox: {
                    BoundingboxAttachment box;
                    attachment.path = attachment.name;
                    box.vertexCount = readVarint(input, true);
                    readVertices(input, box.vertices, box.vertexCount);
                    if (skeletonData->nonessential) {
                        Color color = readColor(input);
                        if (color != Color{0xff, 0xff, 0xff, 0xff}) box.color = color;
                    }
                    attachment.data = box;
                    break;
                }
                case AttachmentType_Mesh: {
                    MeshAttachment mesh;
                    mesh.width = mesh.height = 0.0f;
                    auto path = readString(input);
                    attachment.path = (path.has_value() && !path->empty()) ? path.value() : attachment.name;
                    Color color = readColor(input);
                    if (color != Color{0xff, 0xff, 0xff, 0xff}) mesh.color = color;
                    int vertexCount = readVarint(input, true);
                    readFloatArray(input, vertexCount << 1, mesh.uvs);
                    readShortArray(input, mesh.triangles);
                    readVertices(input, mesh.vertices, vertexCount);
                    mesh.hullLength = readVarint(input, true);
                    if (skeletonData->nonessential) {
                        readShortArray(input, mesh.edges);
                        mesh.width = readFloat(input);
                        mesh.height = readFloat(input);
                    }
                    attachment.data = mesh;
                    break;
                }
                case AttachmentType_Linkedmesh: {
                    LinkedmeshAttachment linkedMesh;
                    linkedMesh.width = linkedMesh.height = 0.0f;
                    auto path = readString(input);
                    attachment.path = (path.has_value() && !path->empty()) ? path.value() : attachment.name;
                    Color color = readColor(input);
                    if (color != Color{0xff, 0xff, 0xff, 0xff}) linkedMesh.color = color;
                    linkedMesh.skin = readString(input);
                    linkedMesh.parentMesh = readString(input).value();
                    linkedMesh.timelines = readBoolean(input) ? 1 : 0;
                    if (skeletonData->nonessential) {
                        linkedMesh.width = readFloat(input);
                        linkedMesh.height = readFloat(input);
                    }
                    attachment.data = linkedMesh;
                    break;
                }
                case AttachmentType_Path: {
                    PathAttachment path;
                    attachment.path = attachment.name;
                    path.closed = readBoolean(input);
                    path.constantSpeed = readBoolean(input);
                    path.vertexCount = readVarint(input, true);
                    readVertices(input, path.vertices, path.vertexCount);
                    readFloatArray(input, path.vertexCount / 3, path.lengths);
                    if (skeletonData->nonessential) {
                        Color color = readColor(input);
                        if (color != Color{0xff, 0xff, 0xff, 0xff}) path.color = color;
                    }
                    attachment.data = path;
                    break;
                }
                default:
                    throw std::runtime_error("Unsupported attachment type for Spine 3.3/3.4");
            }
            skin.attachments[slotName][attachmentName] = attachment;
        }
    }
    return skin;
}

Animation readAnimation(DataInput* input, SkeletonData* skeletonData) {
    Animation animation;
    animation.name = readString(input).value();
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string slotName = skeletonData->slots.at(readVarint(input, true)).name.value();
        MultiTimeline slotTimeline;
        for (int ii = 0, nn = readVarint(input, true); ii < nn; ii++) {
            int timelineType = static_cast<int>(readByte(input));
            int frameCount = readVarint(input, true);
            switch (timelineType) {
                case 0: {  // SLOT_ATTACHMENT
                    Timeline timeline;
                    for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
                        TimelineFrame frame;
                        frame.time = readFloat(input);
                        frame.str1 = readString(input);
                        timeline.push_back(frame);
                    }
                    slotTimeline["attachment"] = timeline;
                    break;
                }
                case 1: {  // SLOT_COLOR
                    Timeline timeline;
                    for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
                        TimelineFrame frame;
                        frame.time = readFloat(input);
                        frame.color1 = readColor(input);
                        if (frameIndex < frameCount - 1) readCurve(input, frame);
                        timeline.push_back(frame);
                    }
                    slotTimeline["rgba"] = timeline;
                    break;
                }
            }
        }
        animation.slots[slotName] = slotTimeline;
    }
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string boneName = skeletonData->bones.at(readVarint(input, true)).name.value();
        MultiTimeline boneTimeline;
        for (int ii = 0, nn = readVarint(input, true); ii < nn; ii++) {
            int timelineType = static_cast<int>(readByte(input));
            int frameCount = readVarint(input, true);
            switch (timelineType) {
                case 0: {  // BONE_ROTATE
                    boneTimeline["rotate"] = readTimeline(input, frameCount, 1);
                    break;
                }
                case 1: {  // BONE_TRANSLATE
                    boneTimeline["translate"] = readTimeline(input, frameCount, 2);
                    break;
                }
                case 2: {  // BONE_SCALE
                    boneTimeline["scale"] = readTimeline(input, frameCount, 2);
                    break;
                }
                case 3: {  // BONE_SHEAR
                    boneTimeline["shear"] = readTimeline(input, frameCount, 2);
                    break;
                }
            }
        }
        animation.bones[boneName] = boneTimeline;
    }
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string ikName = skeletonData->ikConstraints.at(readVarint(input, true)).name.value();
        int frameCount = readVarint(input, true);
        Timeline timeline;
        for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
            TimelineFrame frame;
            frame.time = readFloat(input);
            frame.value1 = readFloat(input);
            frame.bendPositive = readSByte(input) > 0;
            if (frameIndex < frameCount - 1) readCurve(input, frame);
            timeline.push_back(frame);
        }
        animation.ik[ikName] = timeline;
    }
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string transformName = skeletonData->transformConstraints.at(readVarint(input, true)).name.value();
        int frameCount = readVarint(input, true);
        Timeline timeline;
        for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
            TimelineFrame frame;
            frame.time = readFloat(input);
            frame.value1 = readFloat(input);
            frame.value2 = readFloat(input);
            frame.value3 = frame.value2;
            frame.value4 = readFloat(input);
            frame.value5 = frame.value4;
            frame.value6 = readFloat(input);
            if (frameIndex < frameCount - 1) readCurve(input, frame);
            timeline.push_back(frame);
        }
        animation.transform[transformName] = timeline;
    }
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string pathName = skeletonData->pathConstraints.at(readVarint(input, true)).name.value();
        MultiTimeline pathTimeline;
        for (int ii = 0, nn = readVarint(input, true); ii < nn; ii++) {
            PathTimelineType timelineType = static_cast<PathTimelineType>(readByte(input));
            int frameCount = readVarint(input, true);
            switch (timelineType) {
                case PATH_POSITION: {
                    pathTimeline["position"] = readTimeline(input, frameCount, 1);
                    break;
                }
                case PATH_SPACING: {
                    pathTimeline["spacing"] = readTimeline(input, frameCount, 1);
                    break;
                }
                case PATH_MIX: {
                    Timeline timeline;
                    for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
                        TimelineFrame frame;
                        frame.time = readFloat(input);
                        frame.value1 = readFloat(input);
                        frame.value2 = readFloat(input);
                        frame.value3 = frame.value2;
                        if (frameIndex < frameCount - 1) readCurve(input, frame);
                        timeline.push_back(frame);
                    }
                    pathTimeline["mix"] = timeline;
                    break;
                }
            }
        }
        animation.path[pathName] = pathTimeline;
    }
    for (int i = 0, n = readVarint(input, true); i < n; i++) {
        std::string skinName = skeletonData->skins.at(readVarint(input, true)).name;
        for (int ii = 0, nn = readVarint(input, true); ii < nn; ii++) {
            std::string slotName = skeletonData->slots.at(readVarint(input, true)).name.value();
            for (int iii = 0, nnn = readVarint(input, true); iii < nnn; iii++) {
                std::string attachmentName = readString(input).value();
                Timeline attachmentTimeline;
                int frameCount = readVarint(input, true);
                for (int frameIndex = 0; frameIndex < frameCount; frameIndex++) {
                    TimelineFrame frame;
                    frame.time = readFloat(input);
                    size_t end = (size_t) readVarint(input, true);
                    if (end != 0) {
                        size_t start = (size_t) readVarint(input, true);
                        frame.int1 = start;
                        end += start;
                        for (size_t v = start; v < end; v++)
                            frame.vertices.push_back(readFloat(input));
                    }
                    if (frameIndex < frameCount - 1) readCurve(input, frame);
                    attachmentTimeline.push_back(frame);
                }
                animation.attachments[skinName][slotName][attachmentName]["deform"] = attachmentTimeline;
            }
        }
    }
    size_t drawOrderCount = (size_t) readVarint(input, true);
    for (size_t i = 0; i < drawOrderCount; i++) {
        TimelineFrame frame;
        frame.time = readFloat(input);
        size_t offsetCount = (size_t) readVarint(input, true);
        for (size_t ii = 0; ii < offsetCount; ii++) {
            frame.offsets.push_back({
                skeletonData->slots.at(readVarint(input, true)).name.value(),
                readVarint(input, true)
            });
        }
        animation.drawOrder.push_back(frame);
    }
    int eventCount = readVarint(input, true);
    for (int i = 0; i < eventCount; i++) {
        TimelineFrame frame;
        frame.time = readFloat(input);
        int eventIndex = readVarint(input, true);
        const EventData& eventData = skeletonData->events.at(eventIndex);
        frame.str1 = eventData.name;
        frame.int1 = readVarint(input, false);
        frame.value1 = readFloat(input);
        bool freeString = readBoolean(input);
        frame.str2 = freeString ? readString(input) : eventData.stringValue;
        animation.events.push_back(frame);
    }
    return animation;
}

SkeletonData readBinaryData(const Binary& binary) {
    SkeletonData skeletonData;
    DataInput input;
    input.cursor = binary.data();
    input.end = binary.data() + binary.size();

    skeletonData.hashString = readString(&input);
    if (skeletonData.hashString) skeletonData.hash = base64ToUint64(*skeletonData.hashString);
    skeletonData.version = readString(&input).value();

    skeletonData.width = readFloat(&input);
    skeletonData.height = readFloat(&input);

    skeletonData.nonessential = readBoolean(&input);

    if (skeletonData.nonessential) {
        skeletonData.imagesPath = readString(&input);
    }

    /* Bones */
    int numBones = readVarint(&input, true);
    for (int i = 0; i < numBones; i++) {
        BoneData boneData;
        boneData.name = readString(&input);
        if (i != 0) boneData.parent = skeletonData.bones.at(readVarint(&input, true)).name;
        boneData.rotation = readFloat(&input);
        boneData.x = readFloat(&input);
        boneData.y = readFloat(&input);
        boneData.scaleX = readFloat(&input);
        boneData.scaleY = readFloat(&input);
        boneData.shearX = readFloat(&input);
        boneData.shearY = readFloat(&input);
        boneData.length = readFloat(&input);
        bool inheritRotation = readBoolean(&input);
        bool inheritScale = readBoolean(&input);
        boneData.inherit = inheritRotation
            ? (inheritScale ? Inherit_Normal : Inherit_NoScaleOrReflection)
            : (inheritScale ? Inherit_NoRotationOrReflection : Inherit_OnlyTranslation);
        if (skeletonData.nonessential) {
            Color color = readColor(&input);
            if (color != Color{0x9b, 0x9b, 0x9b, 0xff}) boneData.color = color;
        }
        skeletonData.bones.push_back(boneData);
    }

    /* Slots */
    int slotCount = readVarint(&input, true);
    for (int i = 0; i < slotCount; i++) {
        SlotData slotData;
        slotData.name = readString(&input);
        slotData.bone = skeletonData.bones.at(readVarint(&input, true)).name;
        Color color = readColor(&input);
        if (color != Color{0xff, 0xff, 0xff, 0xff}) slotData.color = color;
        slotData.attachmentName = readString(&input);
        slotData.blendMode = static_cast<BlendMode>(readVarint(&input, true));
        skeletonData.slots.push_back(slotData);
    }

    /* IK constraints */
    int ikConstraintsCount = readVarint(&input, true);
    for (int i = 0; i < ikConstraintsCount; i++) {
        IKConstraintData ikData;
        ikData.name = readString(&input);
        int bonesCount = readVarint(&input, true);
        for (int ii = 0; ii < bonesCount; ii++)
            ikData.bones.push_back(skeletonData.bones.at(readVarint(&input, true)).name.value());
        ikData.target = skeletonData.bones.at(readVarint(&input, true)).name;
        ikData.mix = readFloat(&input);
        ikData.bendPositive = readSByte(&input) > 0;
        skeletonData.ikConstraints.push_back(ikData);
    }

    /* Transform constraints */
    int transformConstraintsCount = readVarint(&input, true);
    for (int i = 0; i < transformConstraintsCount; i++) {
        TransformConstraintData transformData;
        transformData.name = readString(&input);
        int bonesCount = readVarint(&input, true);
        for (int ii = 0; ii < bonesCount; ii++)
            transformData.bones.push_back(skeletonData.bones.at(readVarint(&input, true)).name.value());
        transformData.target = skeletonData.bones.at(readVarint(&input, true)).name;
        transformData.offsetRotation = readFloat(&input);
        transformData.offsetX = readFloat(&input);
        transformData.offsetY = readFloat(&input);
        transformData.offsetScaleX = readFloat(&input);
        transformData.offsetScaleY = readFloat(&input);
        transformData.offsetShearY = readFloat(&input);
        transformData.mixRotate = readFloat(&input);
        transformData.mixX = readFloat(&input);
        transformData.mixY = transformData.mixX;
        transformData.mixScaleX = readFloat(&input);
        transformData.mixScaleY = transformData.mixScaleX;
        transformData.mixShearY = readFloat(&input);
        skeletonData.transformConstraints.push_back(transformData);
    }

    /* Path constraints */
    int pathConstraintsCount = readVarint(&input, true);
    for (int i = 0; i < pathConstraintsCount; i++) {
        PathConstraintData pathData;
        pathData.name = readString(&input);
        int bonesCount = readVarint(&input, true);
        for (int ii = 0; ii < bonesCount; ii++)
            pathData.bones.push_back(skeletonData.bones.at(readVarint(&input, true)).name.value());
        pathData.target = skeletonData.slots.at(readVarint(&input, true)).name;
        pathData.positionMode = static_cast<PositionMode>(readVarint(&input, true));
        pathData.spacingMode = static_cast<SpacingMode>(readVarint(&input, true));
        pathData.rotateMode = static_cast<RotateMode>(readVarint(&input, true));
        pathData.offsetRotation = readFloat(&input);
        pathData.position = readFloat(&input);
        pathData.spacing = readFloat(&input);
        pathData.mixRotate = readFloat(&input);
        pathData.mixX = readFloat(&input);
        pathData.mixY = pathData.mixX;
        skeletonData.pathConstraints.push_back(pathData);
    }

    /* Skins */
    Skin defaultSkin = readSkin(&input, true, &skeletonData);
    if (!defaultSkin.attachments.empty()) skeletonData.skins.push_back(defaultSkin);
    int skinCount = readVarint(&input, true);
    for (int i = 0; i < skinCount; i++) {
        skeletonData.skins.push_back(readSkin(&input, false, &skeletonData));
    }

    /* Events */
    int eventCount = readVarint(&input, true);
    for (int i = 0; i < eventCount; i++) {
        EventData eventData;
        eventData.name = readString(&input).value();
        eventData.intValue = readVarint(&input, false);
        eventData.floatValue = readFloat(&input);
        eventData.stringValue = readString(&input);
        skeletonData.events.push_back(eventData);
    }

    /* Animations */
    int animationCount = readVarint(&input, true);
    for (int i = 0; i < animationCount; i++) {
        Animation animation = readAnimation(&input, &skeletonData);
        skeletonData.animations.push_back(animation);
    }

    convertOrder34ToAbove(skeletonData);
    if (input.cursor != input.end)
        throw std::runtime_error("Unexpected trailing skeleton data");
    return skeletonData;
}

}
