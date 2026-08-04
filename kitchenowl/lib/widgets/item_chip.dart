import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:kitchenowl/item_icons.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/services/storage/storage.dart';

class ItemChip extends StatelessWidget {
  final Item item;
  final String? description;

  const ItemChip({
    super.key,
    required this.item,
    this.description,
  });

  @override
  Widget build(BuildContext context) {
    Widget? avatarWidget;
    if (item.icon != null && item.icon!.contains('.')) {
      avatarWidget = CircleAvatar(
        backgroundColor: Colors.transparent,
        backgroundImage: getImageProvider(context, item.icon!, maxWidth: 64),
      );
    } else {
      IconData? icon = ItemIcons.get(item);
      avatarWidget = icon != null ? Icon(icon) : null;
    }

    return Chip(
      avatar: avatarWidget,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      padding: EdgeInsets.zero,
      labelPadding:
          avatarWidget != null ? const EdgeInsets.only(left: 1, right: 4) : null,
      label: Text(item.name +
          (description != null
              ? description!.isNotEmpty
                  ? " (${_limitString(description!)})"
                  : ""
              : item is ItemWithDescription &&
                      (item as ItemWithDescription).description.isNotEmpty
                  ? " (${_limitString((item as ItemWithDescription).description)})"
                  : "")),
    );
  }

  String _limitString(String s) {
    return s.length > 15 ? "${s.substring(0, math.min(15, s.length))}..." : s;
  }
}
