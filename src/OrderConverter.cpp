#include "SkeletonData.h"

void convertOrder34ToAbove(SkeletonData& skeleton) {
    // Older formats apply IK by bone depth (later entries first on ties),
    // then paths, then transform constraints. Newer formats need explicit orders.
    std::map<std::string, size_t> depths;
    for (const auto& bone : skeleton.bones)
        depths[bone.name.value()] = bone.parent ? depths.at(*bone.parent) + 1 : 0;

    std::vector<size_t> ikOrder;
    for (size_t i = 0; i < skeleton.ikConstraints.size(); i++)
        ikOrder.push_back(i);
    std::sort(ikOrder.begin(), ikOrder.end(), [&](size_t a, size_t b) {
        size_t depthA = depths.at(skeleton.ikConstraints[a].bones.at(0));
        size_t depthB = depths.at(skeleton.ikConstraints[b].bones.at(0));
        return depthA != depthB ? depthA < depthB : a > b;
    });
    size_t order = 0;
    for (size_t index : ikOrder)
        skeleton.ikConstraints[index].order = order++;
    for (auto& path : skeleton.pathConstraints)
        path.order = order++;
    for (auto& transform : skeleton.transformConstraints)
        transform.order = order++;
}

void convertOrder42ToBelow(SkeletonData& skeleton) {
    std::vector<size_t> orders; 
    for (auto& ik : skeleton.ikConstraints)
        orders.push_back(ik.order); 
    for (auto& transform : skeleton.transformConstraints)
        orders.push_back(transform.order);
    for (auto& path : skeleton.pathConstraints)
        orders.push_back(path.order);
    std::sort(orders.begin(), orders.end());
    orders.erase(std::unique(orders.begin(), orders.end()), orders.end());
    for (auto& ik : skeleton.ikConstraints) {
        auto it = std::find(orders.begin(), orders.end(), ik.order);
        if (it != orders.end())
            ik.order = std::distance(orders.begin(), it);
    }
    for (auto& transform : skeleton.transformConstraints) {
        auto it = std::find(orders.begin(), orders.end(), transform.order);
        if (it != orders.end())
            transform.order = std::distance(orders.begin(), it);
    }
    for (auto& path : skeleton.pathConstraints) {
        auto it = std::find(orders.begin(), orders.end(), path.order);
        if (it != orders.end())
            path.order = std::distance(orders.begin(), it);
    }
}