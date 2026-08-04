import 'package:flutter/material.dart';
import 'package:kitchenowl/item_icons.dart';
import 'package:kitchenowl/kitchenowl.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/services/api/api_service.dart';
import 'package:kitchenowl/services/api/agent.dart';

class IconSelectionPage extends StatefulWidget {
  final String? oldIcon;
  final String name;
  final Household? household;

  const IconSelectionPage({
    super.key,
    this.oldIcon,
    required this.name,
    this.household,
  });

  @override
  State<IconSelectionPage> createState() => _IconSelectionPageState();
}

class _IconSelectionPageState extends State<IconSelectionPage> {
  TextEditingController searchController = TextEditingController();
  String filter = "";
  bool _generating = false;

  Future<void> _generateIcon() async {
    if (widget.household == null) return;
    setState(() => _generating = true);
    final filename = await ApiService.getInstance().generateIcon(
      widget.household!,
      widget.name,
    );
    if (!mounted) return;
    setState(() => _generating = false);
    if (filename != null) {
      Navigator.of(context).pop(Nullable(filename));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.error),
        ),
      );
    }
  }

  @override
  void dispose() {
    searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.name),
        actions: [
          if (widget.household != null)
            _generating
                ? const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16.0),
                    child: Center(
                      child: SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                  )
                : IconButton(
                    icon: const Icon(Icons.auto_awesome),
                    tooltip: "Generate with AI",
                    onPressed: _generateIcon,
                  ),
          if (widget.oldIcon != null)
            IconButton(
              icon: const Icon(Icons.not_interested_rounded),
              tooltip: AppLocalizations.of(context)!.remove,
              onPressed: () =>
                  Navigator.of(context).pop(const Nullable<String?>.empty()),
            ),
        ],
      ),
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: SizedBox(
              height: 70,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
                child: SearchTextField(
                  controller: searchController,
                  clearOnSubmit: false,
                  onSearch: (s) async {
                    setState(() => filter = s.toLowerCase());
                  },
                  textInputAction: TextInputAction.search,
                ),
              ),
            ),
          ),
          SliverItemGridList(
            items: ItemIcons.map.keys
                .where((e) => e.contains(filter))
                .map((e) => Item(name: e, icon: e))
                .toList(),
            selected: (item) => item.icon == widget.oldIcon,
            onLongPressed: const Nullable<void Function(Item)>.empty(),
            shoppingListStyle: const ShoppingListStyle(allRaised: true),
            onPressed: Nullable((Item item) {
              if (item.icon == widget.oldIcon) {
                Navigator.of(context).pop(const Nullable<String?>.empty());
              } else {
                Navigator.of(context).pop(Nullable(item.icon));
              }
            }),
          ),
        ],
      ),
    );
  }
}
